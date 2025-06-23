"""Stub file for spacy"""

from typing import Any, Dict, List, Optional

def load(model_name: str) -> Any:
    pass

def blank(lang: str) -> Any:
    pass

class Language:
    def __call__(self, text: str) -> Any:
        pass

    def pipe(self, texts: List[str], batch_size: int = 100) -> Any:
        pass

    def add_pipe(self, name: str, config: Optional[Dict[str, Any]] = None) -> None:
        pass

__all__ = ["load", "blank", "Language"]
