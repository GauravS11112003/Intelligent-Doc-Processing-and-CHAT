"""
Patch chromadb config.py for Python 3.14 compatibility.
Run after `pip install -r requirements.txt` if using Python 3.14+.

See: https://github.com/chroma-core/chroma/issues/5996
"""

import sys
import importlib
from pathlib import Path


def patch():
    if sys.version_info < (3, 14):
        print("Python < 3.14 detected — no patch needed.")
        return

    try:
        import chromadb
    except Exception:
        spec = importlib.util.find_spec("chromadb")
        if spec is None or spec.submodule_search_locations is None:
            print("chromadb is not installed — nothing to patch.")
            return

    spec = importlib.util.find_spec("chromadb")
    if spec is None or spec.submodule_search_locations is None:
        print("chromadb is not installed — nothing to patch.")
        return

    pkg_dir = Path(list(spec.submodule_search_locations)[0])
    config_path = pkg_dir / "config.py"

    if not config_path.exists():
        print(f"config.py not found at {config_path}")
        return

    code = config_path.read_text(encoding="utf-8")

    # Already patched?
    if "pydantic_settings" in code:
        print("chromadb config.py is already patched.")
        return

    # 1. Replace the import block
    old_import = (
        'in_pydantic_v2 = False\n'
        'try:\n'
        '    from pydantic import BaseSettings\n'
        'except ImportError:\n'
        '    in_pydantic_v2 = True\n'
        '    from pydantic.v1 import BaseSettings\n'
        '    from pydantic.v1 import validator\n'
        '\n'
        'if not in_pydantic_v2:\n'
        '    from pydantic import validator  # type: ignore # noqa'
    )

    new_import = (
        'import sys\n'
        '\n'
        'in_pydantic_v2 = True\n'
        'if sys.version_info >= (3, 14):\n'
        '    from pydantic_settings import BaseSettings\n'
        '\n'
        '    def validator(*args, **kwargs):  # type: ignore\n'
        '        def decorator(func):  # type: ignore\n'
        '            return func\n'
        '        return decorator\n'
        'else:\n'
        '    try:\n'
        '        from pydantic import BaseSettings\n'
        '        in_pydantic_v2 = False\n'
        '        from pydantic import validator  # type: ignore # noqa\n'
        '    except (ModuleNotFoundError, ImportError, AttributeError):\n'
        '        from pydantic.v1 import BaseSettings  # type: ignore\n'
        '        from pydantic.v1 import validator  # type: ignore'
    )

    if old_import not in code:
        print("WARNING: Could not find original import block to replace.")
        print("The file may have been modified already or chromadb version changed.")
        return

    code = code.replace(old_import, new_import)

    # 2. Add type annotations to untyped fields
    code = code.replace(
        '    chroma_coordinator_host = "localhost"',
        '    chroma_coordinator_host: str = "localhost"',
    )
    code = code.replace(
        '    chroma_logservice_host = "localhost"\n'
        '    chroma_logservice_port = 50052',
        '    chroma_logservice_host: str = "localhost"\n'
        '    chroma_logservice_port: int = 50052',
    )

    # 3. Add extra = "ignore" to Config class
    code = code.replace(
        '    class Config:\n'
        '        env_file = ".env"\n'
        '        env_file_encoding = "utf-8"',
        '    class Config:\n'
        '        env_file = ".env"\n'
        '        env_file_encoding = "utf-8"\n'
        '        extra = "ignore"',
    )

    config_path.write_text(code, encoding="utf-8")
    print(f"Successfully patched {config_path}")


if __name__ == "__main__":
    patch()
