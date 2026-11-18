"""
Abstract base class for storage providers.
"""
from abc import ABC, abstractmethod
from typing import BinaryIO, Union, Optional


class BaseStorage(ABC):
    """Abstract file storage provider interface."""

    @abstractmethod
    def save_file(self, file_data: Union[bytes, BinaryIO, str], key: str, content_type: Optional[str] = None) -> str:
        """
        Store a file into the storage backend.
        :param file_data: File bytes, file-like object, or existing local path.
        :param key: Unique destination key (path).
        :param content_type: MIME type of the file.
        :return: Final storage key or identifier.
        """
        pass

    @abstractmethod
    def get_file(self, key: str, local_destination: Optional[str] = None) -> Union[bytes, str]:
        """
        Retrieve file content as bytes or download to local path.
        :param key: Storage key.
        :param local_destination: Optional destination path on local disk.
        :return: File bytes if local_destination is None, else the destination path.
        """
        pass

    @abstractmethod
    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate a URL (presigned S3 URL or public/internal URL) to access the file.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a file key exists."""
        pass

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Delete a file by key."""
        pass

