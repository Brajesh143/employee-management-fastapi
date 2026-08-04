import hashlib
import secrets


class Hash:

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plain-text password using SHA-256 with a random salt.
        """
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def verify_password(
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """
        Verify a plain-text password against a stored hash.
        """
        if not hashed_password or "$" not in hashed_password:
            return False

        salt, digest = hashed_password.split("$", 1)
        salt = salt[:-1] if salt.endswith(":") else salt
        expected = hashlib.sha256(f"{salt}:{plain_password}".encode("utf-8")).hexdigest()
        return secrets.compare_digest(expected, digest)