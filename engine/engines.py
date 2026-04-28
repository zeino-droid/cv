import json
import os
import subprocess
from typing import Optional

# Configuration
OLLAMA_FALLBACK_MODELS = [
    "mistral:7b-instruct-v0.3-q4_K_M",
    "mistral:latest",
    "phi3:mini",
    "llama3.2:3b",
]


class LLMEngine:
    """Base class for LLM engines"""

    def is_ready(self) -> bool:
        raise NotImplementedError

    async def generate(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        raise NotImplementedError


class OllamaEngine(LLMEngine):
    """Interface avec Ollama pour la rédaction IA locale"""

    def __init__(self):
        self.model = None
        self.available = False
        self._detect()

    def _detect(self):
        """Détecte si Ollama est disponible et quel modèle utiliser"""
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                installed_models = result.stdout.lower()
                for model_name in OLLAMA_FALLBACK_MODELS:
                    base_name = model_name.split(":")[0]
                    if base_name in installed_models:
                        self.model = model_name
                        self.available = True
                        return
                self.available = True
                self.model = None
            else:
                self.available = False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.available = False

    def is_ready(self) -> bool:
        return self.available and self.model is not None

    async def generate(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        if not self.is_ready():
            return None
        try:
            try:
                import ollama as ollama_lib

                response = ollama_lib.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        "temperature": temperature,
                        "top_p": 0.9,
                        "num_predict": 2048,
                    },
                )
                return response.get("response", "")
            except ImportError:
                payload = json.dumps(
                    {
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "top_p": 0.9,
                            "num_predict": 2048,
                        },
                    }
                )
                result = subprocess.run(
                    [
                        "curl",
                        "-s",
                        "http://localhost:11434/api/generate",
                        "-d",
                        payload,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    try:
                        return json.loads(result.stdout).get("response", "")
                    except json.JSONDecodeError:
                        print("   ⚠️  Réponse Ollama invalide (JSON)")
                        return None
                print(f"   ⚠️  Appel curl Ollama échoué (code {result.returncode})")
        except (OSError, RuntimeError, ValueError) as e:
            print(f"   ⚠️  Erreur Ollama: {e}")
        return None

    def pull_model(self, model_name: str = None) -> bool:
        model = model_name or OLLAMA_FALLBACK_MODELS[0]
        print(f"\n   📥 Téléchargement du modèle {model}...")
        try:
            result = subprocess.run(["ollama", "pull", model], timeout=1800)
            if result.returncode == 0:
                self.model = model
                return True
        except (OSError, RuntimeError, ValueError) as e:
            print(f"   ❌ Erreur: {e}")
        return False


class MLXEngine(LLMEngine):
    """Interface avec mlx-lm pour Apple Silicon"""

    def __init__(self, model_name: str = "mlx-community/Mistral-7B-Instruct-v0.3-4bit"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.available = False
        self._detect()

    def _detect(self):
        try:
            import mlx_lm

            self.available = True
        except ImportError:
            self.available = False

    def _load_model(self):
        if self.model is not None:
            return True
        try:
            from mlx_lm import load

            print(f"   📥 Chargement MLX ({self.model_name})...")
            self.model, self.tokenizer = load(self.model_name)
            return True
        except (ImportError, OSError, RuntimeError, ValueError) as e:
            print(f"   ⚠️  Erreur MLX: {e}")
            return False

    def is_ready(self) -> bool:
        return self.available

    async def generate(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        if not self.available or not self._load_model():
            return None
        try:
            from mlx_lm import generate as mlx_generate
            from mlx_lm.sample_utils import make_sampler

            formatted_prompt = f"[INST] {prompt} [/INST]"
            sampler = make_sampler(temp=temperature, top_p=0.9)
            result = mlx_generate(
                self.model,
                self.tokenizer,
                prompt=formatted_prompt,
                max_tokens=1024,
                sampler=sampler,
            )
            return result.strip()
        except (ImportError, OSError, RuntimeError, ValueError) as e:
            print(f"   ⚠️  Erreur MLX: {e}")
            return None


class GeminiEngine(LLMEngine):
    """Interface avec Google Gemini via l'API (Cloud Native).

    Stocke la dernière erreur dans `self.last_error` pour que l'UI puisse
    afficher un message clair (clé absente vs quota épuisé vs autre).
    En cas de quota épuisé (429) sur le modèle principal, tente un
    fallback automatique sur des modèles alternatifs ayant leurs propres
    quotas free-tier.
    """

    # Chaîne de fallback : chaque modèle a son propre quota free tier.
    # Vérifiée via client.models.list() — on ne liste que des modèles qui
    # existent et supportent generateContent. Les anciens 1.5/exp sont retirés
    # car ils renvoient 404 sur l'API v1beta actuelle.
    FALLBACK_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-lite-latest",
    ]

    def __init__(self, api_key: str = None, model_name: str = None):
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.available = False
        self.client = None
        self.genai = None
        self.last_error: Optional[str] = None  # ex "quota_exceeded", "no_key", "blocked", "network", "empty"
        self.last_error_message: Optional[str] = None
        self._detect()

    def _detect(self):
        if not self.api_key:
            self.last_error = "no_key"
            self.last_error_message = "Aucune clé GEMINI_API_KEY trouvée dans l'environnement."
            return
        try:
            from google import genai
            self.genai = genai
            self.client = genai.Client(api_key=self.api_key)
            self.available = True
        except ImportError:
            self.available = False
            self.last_error = "missing_library"
            self.last_error_message = "Le package google-genai n'est pas installé."

    def is_ready(self) -> bool:
        return self.available and self.client is not None

    def _try_one(self, model: str, prompt: str, temperature: float) -> Optional[str]:
        """Tente un appel Gemini sur un modèle donné. Renvoie le texte ou None
        et met à jour self.last_error/last_error_message en cas d'échec."""
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=self.genai.types.GenerateContentConfig(
                    temperature=temperature,
                    top_p=0.9,
                    max_output_tokens=2048,
                ),
            )
            text = getattr(response, "text", None)
            if text and text.strip():
                self.last_error = None
                self.last_error_message = None
                return text.strip()
            self.last_error = "empty"
            self.last_error_message = (
                f"Modèle {model} a renvoyé une réponse vide "
                f"(souvent : prompt trop court ou bloqué par le filtre de sécurité)."
            )
            return None
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                self.last_error = "quota_exceeded"
                self.last_error_message = (
                    f"Quota gratuit Gemini épuisé sur {model} "
                    f"(20 req/jour/modèle en free tier). Réessaye demain "
                    f"ou ajoute la facturation dans https://aistudio.google.com."
                )
            elif "PERMISSION_DENIED" in msg or "401" in msg or "403" in msg:
                self.last_error = "auth_failed"
                self.last_error_message = f"Clé Gemini refusée par l'API ({model})."
            elif "blocked" in msg.lower() or "safety" in msg.lower():
                self.last_error = "blocked"
                self.last_error_message = "Réponse bloquée par les filtres de sécurité Gemini."
            else:
                self.last_error = "api_error"
                self.last_error_message = f"Erreur Gemini ({model}) : {msg[:200]}"
            print(f"   ⚠️  Erreur Gemini ({model}): {msg[:300]}")
            return None

    async def generate(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        if not self.is_ready():
            return None

        # 1) Modèle principal demandé
        text = self._try_one(self.model_name, prompt, temperature)
        if text:
            return text

        # 2) Fallback automatique uniquement sur quota épuisé / api_error
        #    (inutile sur no_key/auth_failed/blocked).
        if self.last_error not in ("quota_exceeded", "api_error"):
            return None

        for fb in self.FALLBACK_MODELS:
            if fb == self.model_name:
                continue
            print(f"   ↪︎  Gemini fallback → {fb}")
            text = self._try_one(fb, prompt, temperature)
            if text:
                return text
            # Si ce fallback est aussi en quota épuisé, on continue.
            # Si autre type d'erreur définitif (auth/blocked) → arrêt.
            if self.last_error not in ("quota_exceeded", "api_error", "empty"):
                break
        return None
