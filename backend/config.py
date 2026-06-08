from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
KARPATHYS_URL = os.environ.get("KARPATHYS_URL", "")
BOB_WORKER_INTERVAL_MINUTES = int(os.environ.get("BOB_WORKER_INTERVAL_MINUTES", 5))
BOB_BATCH_SIZE = int(os.environ.get("BOB_BATCH_SIZE", 20))
