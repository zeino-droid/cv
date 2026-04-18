import os
import subprocess
import json
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
                ["ollama", "list"],
                capture_output=True, text=True, timeout=5
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
                    options={"temperature": temperature, "top_p": 0.9, "num_predict": 2048}
                )
                return response.get("response", "")
            except ImportError:
                payload = json.dumps({
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "top_p": 0.9, "num_predict": 2048}
                })
                result = subprocess.run(
                    ["curl", "-s", "http://localhost:11434/api/generate", "-d", payload],
                    capture_output=True, text=True, timeout=120
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
            result = mlx_generate(self.model, self.tokenizer, prompt=formatted_prompt, max_tokens=1024, sampler=sampler)
            return result.strip()
        except (ImportError, OSError, RuntimeError, ValueError) as e:
            print(f"   ⚠️  Erreur MLX: {e}")
            return None

class GeminiEngine(LLMEngine):
    """Interface avec Google Gemini via l'API (Cloud Native)"""
    def __init__(self, api_key: str = None, model_name: str = "gemini-flash-latest"):
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.available = False
        self.model = None
        self._detect()

    def _detect(self):
        try:
            import google.generativeai as genai
            if self.api_key:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.available = True
        except ImportError:
            self.available = False

    def is_ready(self) -> bool:
        return self.available and self.model is not None

    async def generate(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        if not self.is_ready():
            return None
        try:
            import google.generativeai as genai
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    top_p=0.9,
                    max_output_tokens=2048,
                )
            )
            return response.text.strip()
        except Exception as e:
            print(f"   ⚠️  Erreur Gemini: {e}")
            return None
