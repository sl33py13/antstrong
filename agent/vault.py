import hmac
import hashlib
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet


class LocalKeyVault:
    def __init__(self, vault_dir: str = ".antstrong_vault"):
        self.vault_path = Path(vault_dir)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.key_file = self.vault_path / "master.key"
        self.salt_file = self.vault_path / "workspace.salt"
        self.map_file = self.vault_path / "vault.antstrong"

        self._cipher = Fernet(self._load_or_create_key())
        self._salt = self._load_or_create_salt()
        self._lookup: dict[str, dict[str, str]] = self._load_vault()
        self._alias_set: set[str] = set(self._lookup["_aliases"])
        self._token_cache: dict[tuple[str, str], str] = {}

    def _load_or_create_key(self) -> bytes:
        if self.key_file.exists():
            return self.key_file.read_bytes()
        key = Fernet.generate_key()
        self.key_file.write_bytes(key)
        os.chmod(self.key_file, 0o600)
        return key

    def _load_or_create_salt(self) -> bytes:
        if self.salt_file.exists():
            return self.salt_file.read_bytes()
        salt = os.urandom(32)
        self.salt_file.write_bytes(salt)
        os.chmod(self.salt_file, 0o600)
        return salt

    def _load_vault(self) -> dict[str, dict[str, str]]:
        if not self.map_file.exists():
            return {"companies": {}, "technicians": {}, "assets": {}, "_aliases": []}
        decrypted = self._cipher.decrypt(self.map_file.read_bytes())
        data = json.loads(decrypted.decode("utf-8"))
        data.setdefault("_aliases", [])
        return data

    def save(self) -> None:
        raw = json.dumps(self._lookup, indent=2).encode("utf-8")
        encrypted = self._cipher.encrypt(raw)
        self.map_file.write_bytes(encrypted)
        os.chmod(self.map_file, 0o600)

    def tokenise(self, category: str, raw_id: str, display_name: str) -> str:
        prefixes = {"companies": "CL", "technicians": "TC", "assets": "AS"}
        if category not in prefixes:
            raise ValueError(f"Unsupported token category: {category}")

        # The token comes from the source system's ID only. Different exports often
        # spell the same client differently ("Bayside Logistics" vs "Bayside
        # Logistics Pty Ltd"); keying on the name split one client into several tokens.
        cache_key = (category, raw_id.strip())
        token = self._token_cache.get(cache_key)
        if token is None:
            clean_key = f"{category}::{raw_id.strip()}"
            digest = hmac.new(self._salt, clean_key.encode("utf-8"), hashlib.sha256).hexdigest()[:10]
            token = f"{prefixes[category]}_{digest}"
            self._token_cache[cache_key] = token

        name = display_name.strip()
        if name:
            # First non-empty name wins for re-hydration; every spelling is kept so
            # the outbound gate can block all of them.
            self._lookup[category].setdefault(token, name)
            if name not in self._alias_set:
                self._alias_set.add(name)
                self._lookup["_aliases"].append(name)
        else:
            self._lookup[category].setdefault(token, raw_id.strip())
        return token

    def get_rehydration_map(self) -> dict[str, str]:
        flat = {}
        for category, category_map in self._lookup.items():
            if category == "_aliases":
                continue
            flat.update(category_map)
        return flat

    def get_all_real_names(self) -> set[str]:
        """Every real name or spelling ever seen, for the outbound privacy gate."""
        return set(self.get_rehydration_map().values()) | self._alias_set
