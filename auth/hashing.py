import hashlib
import secrets

import bcrypt


class Hash:
    BCRYPT_ROUNDS = 12

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        """
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes.")
        return bcrypt.hashpw(
            password_bytes,
            bcrypt.gensalt(rounds=Hash.BCRYPT_ROUNDS),
        ).decode("ascii")

    @staticmethod
    def verify_password(
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """
        Verify bcrypt hashes and transparently support the previous salted SHA-256 format.
        """
        if not hashed_password:
            return False

        password_bytes = plain_password.encode("utf-8")
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                return bcrypt.checkpw(password_bytes, hashed_password.encode("ascii"))
            except (ValueError, UnicodeEncodeError):
                return False

        if "$" not in hashed_password:
            return False

        salt, digest = hashed_password.split("$", 1)
        expected = hashlib.sha256(f"{salt}:{plain_password}".encode("utf-8")).hexdigest()
        return secrets.compare_digest(expected, digest)

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        return not hashed_password.startswith(("$2a$", "$2b$", "$2y$"))