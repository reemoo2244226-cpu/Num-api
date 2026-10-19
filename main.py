# language: Python, file: main.py, target: Railway / any Linux, Python 3.9+
# *FastAPI wrapper — Num Info Lookup (NaxUpdate API)*

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import uvicorn

app = FastAPI(
    title="Num Info Lookup API",
    description="Mobile number se full info — filtered & emoji-formatted",
    version="4.0.0",
)

# ---------- Config ----------
UPSTREAM_URL = "https://api.naxupdate.workers.dev/api/number-info"
API_KEY = "30Day"
YOUR_CREDIT = "@YoBlackX"
DEVELOPER = "YoBlackX"
REQUEST_TIMEOUT = 40
MAX_RECORDS = 5


async def call_upstream(number: str) -> dict:
    """NaxUpdate API call"""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(
                UPSTREAM_URL,
                params={"key": API_KEY, "number": number},
            )
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return {"_error": "Upstream timeout. Dobara try karo."}
    except httpx.HTTPError as e:
        return {"_error": f"Upstream request failed: {str(e)}"}
    except ValueError:
        return {"_error": "Upstream ne invalid JSON bheja"}


def clean_record(rec: dict) -> dict:
    """NaxUpdate ke field names ko normalize karo"""
    if not isinstance(rec, dict):
        return {}
    return {
        "name": rec.get("name") or "N/A",
        "father_name": rec.get("father_name") or "N/A",
        "address": rec.get("address") or "N/A",
        "mobile": rec.get("mobile") or "N/A",
        "alt_number": rec.get("alt_mobile") or "N/A",
        "Aadhar": rec.get("aadhaar") or "N/A",
        "email": rec.get("email") or "N/A",
        "circle": rec.get("circle") or "N/A",
    }


def dedupe_records(records: list) -> list:
    """Same name+mobile+aadhaar wale duplicates hatao"""
    seen = set()
    out = []
    for r in records:
        key = (r.get("name"), r.get("mobile"), r.get("Aadhar"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_response(number: str, raw: dict) -> dict:
    """Raw NaxUpdate data -> clean output"""
    if "_error" in raw:
        return {
            "success": False,
            "credit": YOUR_CREDIT,
            "developer": DEVELOPER,
            "query": number,
            "message": raw["_error"],
        }

    if not raw.get("success", False):
        return {
            "success": False,
            "credit": YOUR_CREDIT,
            "developer": DEVELOPER,
            "query": number,
            "message": raw.get("message", "No data found"),
        }

    # Naya structure: raw.data.result
    data_node = raw.get("data") or {}
    if not isinstance(data_node, dict) or not data_node.get("found", False):
        return {
            "success": False,
            "credit": YOUR_CREDIT,
            "developer": DEVELOPER,
            "query": number,
            "message": data_node.get("message", "No data found"),
        }

    records = data_node.get("result", []) or []
    if not isinstance(records, list):
        records = []

    cleaned = [clean_record(r) for r in records]
    cleaned = [r for r in cleaned if r]
    cleaned = dedupe_records(cleaned)
    cleaned = cleaned[:MAX_RECORDS]

    key_info = raw.get("key") or {}
    daily_rem = key_info.get("dailyRemaining", "N/A")
    max_rem = key_info.get("maxRemaining", "N/A")

    return {
        "success": True,
        "credit": YOUR_CREDIT,
        "developer": DEVELOPER,
        "query": number,
        "total_records": len(cleaned),
        "data": cleaned,
        "usage": {
            "daily_remaining": daily_rem,
            "max_remaining": max_rem,
        },
        "branding": {
            "developer": DEVELOPER,
            "upstream": raw.get("owner", "N/A"),
        },
    }


def format_pretty(data: dict) -> str:
    if not data.get("success"):
        return (
            f"❌ *Lookup Failed*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *Query:* `{data.get('query', 'N/A')}`\n"
            f"⚠️ *Message:* {data.get('message', 'Unknown error')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💠 *Credit:* {data.get('credit', YOUR_CREDIT)}"
        )

    records = data.get("data", [])
    total = data.get("total_records", 0)
    usage = data.get("usage", {}) or {}

    lines = [
        f"📱 *NUM INFO LOOKUP*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🔍 *Query:* `{data.get('query')}`",
        f"📊 *Records:* {total}",
        f"",
    ]

    for i, r in enumerate(records, 1):
        lines.append(f"┌─── *RECORD {i}* ───┐")
        lines.append(f"👤 *Name:* {r.get('name')}")
        lines.append(f"👨 *Father:* {r.get('father_name')}")
        lines.append(f"📍 *Address:* {str(r.get('address'))[:120]}")
        lines.append(f"📞 *Mobile:* `{r.get('mobile')}`")
        alt = str(r.get('alt_number', 'N/A'))
        if alt.startswith("91") and len(alt) > 10:
            alt = alt[2:]
        lines.append(f"📱 *Alt:* `{alt}`")
        lines.append(f"🆔 *Aadhar:* `{r.get('Aadhar')}`")
        lines.append(f"📧 *Email:* {r.get('email')}")
        lines.append(f"🔄 *Circle:* {r.get('circle')}")
        lines.append(f"└─────────────────────┘")
        lines.append("")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 *Daily Left:* {usage.get('daily_remaining', 'N/A')}")
    lines.append(f"💠 *Credit:* {data.get('credit', YOUR_CREDIT)}")
    lines.append(f"✦ *Developer:* {data.get('developer', DEVELOPER)}")
    return "\n".join(lines)


@app.get("/lookup")
async def lookup(number: str = Query(..., description="10-digit mobile number")):
    number = number.strip().replace("+91", "").replace(" ", "")
    if not number.isdigit() or len(number) != 10:
        raise HTTPException(400, detail={
            "success": False,
            "credit": YOUR_CREDIT,
            "developer": DEVELOPER,
            "message": "Invalid number. Sirf 10 digits, without +91.",
        })
    raw = await call_upstream(number)
    return JSONResponse(content=build_response(number, raw))


@app.get("/lookup/pretty", response_class=PlainTextResponse)
async def lookup_pretty(number: str = Query(..., description="10-digit mobile number")):
    number = number.strip().replace("+91", "").replace(" ", "")
    if not number.isdigit() or len(number) != 10:
        return "❌ Invalid number. Send 10-digit mobile number."
    raw = await call_upstream(number)
    return format_pretty(build_response(number, raw))


@app.get("/")
async def index():
    return {
        "name": "Num Info Lookup API",
        "version": "4.0.0",
        "credit": YOUR_CREDIT,
        "developer": DEVELOPER,
        "endpoints": {
            "/lookup?number=<10digit>": "JSON output",
            "/lookup/pretty?number=<10digit>": "Emoji-formatted text",
            "/docs": "Swagger UI",
            "/health": "Status check",
        },
        "example": "/lookup?number=7355194378",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "credit": YOUR_CREDIT, "developer": DEVELOPER}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)