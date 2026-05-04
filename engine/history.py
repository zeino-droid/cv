import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ProfileHistory:
    """
    Handles Career Versioning and Data Integrity for the master profile.
    Provides snapshotting and optional Git-based versioning.
    """
    
    def __init__(self, profile_path: Path):
        self.profile_path = Path(profile_path)
        self.root_dir = self.profile_path.parent.parent # Assuming profile is in /profiles/
        self.history_dir = self.profile_path.parent / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_with_history(self, data: dict, message: str = "Profile update via Dashboard") -> None:
        """
        Saves the profile and creates a timestamped snapshot.
        Also attempts a git commit if the repository is clean/managed.
        """
        # 1. Create Snapshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"master_profile_{timestamp}.json"
        snapshot_path = self.history_dir / snapshot_filename
        
        # Save snapshot first
        try:
            snapshot_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info(f"✅ Snapshot created: {snapshot_path}")
        except Exception as e:
            logger.error(f"❌ Failed to create snapshot: {e}")

        # 2. Update Main Profile
        try:
            self.profile_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info(f"✅ Main profile updated: {self.profile_path}")
        except Exception as e:
            logger.error(f"❌ Failed to update main profile: {e}")
            raise

        # 3. Git Versioning (Optional / Best Effort)
        self._git_commit(message)
        
        # 4. Cleanup old snapshots (Keep last 50)
        self._cleanup_history(max_keep=50)

    def _git_commit(self, message: str) -> None:
        """Attempts to commit the change to git if in a git repo."""
        try:
            # Check if it's a git repo
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.root_dir, check=True, capture_output=True
            )
            
            # Add the profile file
            subprocess.run(
                ["git", "add", str(self.profile_path.relative_to(self.root_dir))],
                cwd=self.root_dir, check=True
            )
            
            # Check if there are changes to commit
            diff = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=self.root_dir
            )
            
            if diff.returncode != 0: # 0 means no changes
                subprocess.run(
                    ["git", "commit", "-m", f"🛡️ Career Versioning: {message}"],
                    cwd=self.root_dir, check=True
                )
                logger.info("✅ Git commit successful.")
        except Exception as e:
            # Silently fail if git is not available or not a repo
            logger.warning(f"⚠️ Git auto-commit failed (optional): {e}")

    def _cleanup_history(self, max_keep: int = 50) -> None:
        """Keep only the N most recent snapshots."""
        try:
            snapshots = sorted(self.history_dir.glob("master_profile_*.json"), key=lambda p: p.stat().st_mtime)
            if len(snapshots) > max_keep:
                for old_snapshot in snapshots[:-max_keep]:
                    old_snapshot.unlink()
                logger.info(f"🧹 Cleaned up {len(snapshots) - max_keep} old snapshots.")
        except Exception as e:
            logger.warning(f"⚠️ Snapshot cleanup failed: {e}")

    def list_snapshots(self):
        """Returns a list of available snapshots."""
        return sorted(self.history_dir.glob("master_profile_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
