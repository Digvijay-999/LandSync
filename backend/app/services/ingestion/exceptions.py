class IngestionError(Exception):
    """Base exception for all geospatial ingestion failures."""
    def __init__(self, message: str, code: str = "INGESTION_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class UnsupportedFormatError(IngestionError):
    """Raised when file format is not supported or cannot be identified."""
    def __init__(self, message: str):
        super().__init__(message, code="UNSUPPORTED_FORMAT")


class FileTooLargeError(IngestionError):
    """Raised when uploaded file exceeds allowed size limits."""
    def __init__(self, message: str):
        super().__init__(message, code="FILE_TOO_LARGE")


class CorruptedFileError(IngestionError):
    """Raised when file is damaged, unreadable, or invalid geospatial structure."""
    def __init__(self, message: str):
        super().__init__(message, code="CORRUPTED_FILE")


class MissingShapefileComponentsError(IngestionError):
    """Raised when a shapefile archive is missing .shp, .shx, or .dbf."""
    def __init__(self, message: str):
        super().__init__(message, code="MISSING_SHAPEFILE_COMPONENTS")


class MissingCoordinateColumnsError(IngestionError):
    """Raised when CSV has no identifiable latitude/longitude coordinate columns."""
    def __init__(self, message: str):
        super().__init__(message, code="MISSING_COORDINATE_COLUMNS")


class EmptyDatasetError(IngestionError):
    """Raised when dataset contains zero features or records."""
    def __init__(self, message: str):
        super().__init__(message, code="EMPTY_DATASET")


class InvalidCoordinateError(IngestionError):
    """Raised when coordinate values in CSV cannot be parsed to valid numbers."""
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_COORDINATES")


class ProjectNotFoundError(IngestionError):
    """Raised when the target project ID does not exist."""
    def __init__(self, message: str = "Project not found."):
        super().__init__(message, code="PROJECT_NOT_FOUND")

