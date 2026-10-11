from __future__ import annotations

import json
from app.services.runtime import get_runtime_status

if __name__ == "__main__":
    print(json.dumps(get_runtime_status(), ensure_ascii=False, indent=2))
