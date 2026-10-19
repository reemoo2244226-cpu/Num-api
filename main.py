# language: Python, file: main.py, target: Railway / any Linux, Python 3.9+
# *FastAPI wrapper — Num Info Lookup + Aadhaar Family Info*

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import uvicorn

app = FastAPI(
    title="Info Lookup API",
    description="Mobile number + Aadhaar family info — filtered & emoji-formatted",
    version="5.0.0",
)

# ---------- Config ----------
# Number Info (NaxUpdate)
NUMBER_API_URL = "https://api.naxupdate.workers.dev/api/number-info"
NUMBER_API_KEY = "30Day"

# Family Info (Dark Info)
FAMILY_API_URL = "https://dark-info.site/familyinfo/api.php"
FAMILY_API_KEY = "JSON-4325"

YOUR_CREDIT = "@YoBlackX"
DEVELOPER = "YoBlackX"
REQUEST_TIMEOUT = 40
MAX_RECORDS = 5


# ============================================================
#                     NUMBER INFO SECTION
# ============================================================

async def call_number_upstream(number: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(
                NUMBER_API_URL,
                params={"key": NUMBER_API_KEY, "number": number},
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
    seen = set()
    out = []
    for r in records:
        key = (r.get("name"), r.get("mobile"), r.get("Aadhar"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_number_response(number: str, raw: dict) -> dict:
    if "_error" in raw:
        return {
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "query": number, "message": raw["_error"],
        }
    if not raw.get("success", False):
        return {
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "query": number, "message": raw.get("message", "No data found"),
        }

    data_node = raw.get("data") or {}
    if not isinstance(data_node, dict) or not data_node.get("found", False):
        return {
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "query": number, "message": data_node.get("message", "No data found"),
        }

    records = data_node.get("result", []) or []
    if not isinstance(records, list):
        records = []

    cleaned = [clean_record(r) for r in records]
    cleaned = [r for r in cleaned if r]
    cleaned = dedupe_records(cleaned)
    cleaned = cleaned[:MAX_RECORDS]

    key_info = raw.get("key") or {}
    return {
        "success": True,
        "credit": YOUR_CREDIT,
        "developer": DEVELOPER,
        "query": number,
        "total_records": len(cleaned),
        "data": cleaned,
        "usage": {
            "daily_remaining": key_info.get("dailyRemaining", "N/A"),
            "max_remaining": key_info.get("maxRemaining", "N/A"),
        },
    }


def format_number_pretty(data: dict) -> str:
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
    usage = data.get("usage", {}) or {}

    lines = [
        "📱 *NUM INFO LOOKUP*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔍 *Query:* `{data.get('query')}`",
        f"📊 *Records:* {data.get('total_records', 0)}",
        "",
    ]
    for i, r in enumerate(records, 1):
        lines += [
            f"┌─── *RECORD {i}* ───┐",
            f"👤 *Name:* {r.get('name')}",
            f"👨 *Father:* {r.get('father_name')}",
            f"📍 *Address:* {str(r.get('address'))[:120]}",
            f"📞 *Mobile:* `{r.get('mobile')}`",
            f"📱 *Alt:* `{r.get('alt_number')}`",
            f"🆔 *Aadhar:* `{r.get('Aadhar')}`",
            f"📧 *Email:* {r.get('email')}",
            f"🔄 *Circle:* {r.get('circle')}",
            "└─────────────────────┘", "",
        ]
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 *Daily Left:* {usage.get('daily_remaining', 'N/A')}",
        f"💠 *Credit:* {data.get('credit', YOUR_CREDIT)}",
    ]
    return "\n".join(lines)


# ============================================================
#                     FAMILY INFO SECTION
# ============================================================

async def call_family_upstream(aadhar: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(
                FAMILY_API_URL,
                params={"key": FAMILY_API_KEY, "aadhar": aadhar},
            )
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return {"_error": "Upstream timeout. Dobara try karo."}
    except httpx.HTTPError as e:
        return {"_error": f"Upstream request failed: {str(e)}"}
    except ValueError:
        return {"_error": "Upstream ne invalid JSON bheja"}


# Relationship emoji mapping
REL_EMOJI = {
    "SELF": "🙋",
    "FATHER": "👨",
    "MOTHER": "👩",
    "HUSBAND": "👨",
    "WIFE": "👩",
    "SON": "👦",
    "DAUGHTER": "👧",
    "BROTHER": "👨",
    "SISTER": "👩",
    "OTHER": "👤",
}


def clean_family_member(m: dict) -> dict:
    if not isinstance(m, dict):
        return {}
    rel = (m.get("releationship_name") or m.get("relationship_name") or "N/A").upper()
    return {
        "name": m.get("memberName") or "N/A",
        "relationship": rel,
        "masked_aadhar": m.get("maskedUid") or "N/A",
        "member_id": m.get("memberId") or "N/A",
        "has_uid": m.get("uid") or "N/A",
    }


def build_family_response(aadhar: str, raw: dict) -> dict:
    if "_error" in raw:
        return {
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "query": aadhar, "message": raw["_error"],
        }

    if raw.get("status", "").lower() != "success":
        return {
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "query": aadhar,
            "message": raw.get("M-S-G") or raw.get("message") or "No data found",
        }

    data_node = raw.get("data") or {}
    details = data_node.get("ALL-DETAILS") or {}
    if not isinstance(details, dict) or not details:
        return {
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "query": aadhar,
            "message": data_node.get("MSG", "No family details found"),
        }

    members_raw = details.get("memberDetailsList", []) or []
    if not isinstance(members_raw, list):
        members_raw = []

    members = [clean_family_member(m) for m in members_raw]
    members = [m for m in members if m]

    # SELF ko pehle rakho, baaki alphabetical
    members.sort(key=lambda x: (0 if x["relationship"] == "SELF" else 1, x["name"]))

    return {
        "success": True,
        "credit": YOUR_CREDIT,
        "developer": DEVELOPER,
        "query": aadhar,
        "total_members": len(members),
        "ration_card": {
            "rc_id": details.get("rcId", "N/A"),
            "scheme": details.get("schemeName", "N/A"),
            "fps_id": details.get("fpsId", "N/A"),
            "address": details.get("address", "N/A"),
            "district": details.get("homeDistName", "N/A"),
            "state": details.get("homeStateName", "N/A"),
            "onorc_allowed": details.get("allowed_onorc", "N/A"),
        },
        "members": members,
        "timestamp": raw.get("timestamp", "N/A"),
    }


def format_family_pretty(data: dict) -> str:
    if not data.get("success"):
        return (
            f"❌ *Family Lookup Failed*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *Aadhaar:* `{data.get('query', 'N/A')}`\n"
            f"⚠️ *Message:* {data.get('message', 'Unknown error')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💠 *Credit:* {data.get('credit', YOUR_CREDIT)}"
        )

    rc = data.get("ration_card", {}) or {}
    members = data.get("members", [])

    lines = [
        "👨‍👩‍👧‍👦 *FAMILY INFO LOOKUP*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔍 *Aadhaar:* `{data.get('query')}`",
        f"👥 *Members:* {data.get('total_members', 0)}",
        "",
        "🏠 *RATION CARD DETAILS*",
        f"🆔 *RC ID:* `{rc.get('rc_id')}`",
        f"📋 *Scheme:* {rc.get('scheme')}",
        f"🏪 *FPS ID:* `{rc.get('fps_id')}`",
        f"📍 *Address:* {str(rc.get('address'))[:120]}",
        f"🗺️ *District:* {rc.get('district')}",
        f"🏛️ *State:* {rc.get('state')}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "👥 *FAMILY MEMBERS*",
        "",
    ]

    for i, m in enumerate(members, 1):
        emoji = REL_EMOJI.get(m["relationship"], "👤")
        lines += [
            f"┌─── *MEMBER {i}* ───┐",
            f"{emoji} *Name:* {m.get('name')}",
            f"🔗 *Relation:* {m.get('relationship')}",
            f"🆔 *Masked Aadhaar:* `{m.get('masked_aadhar')}`",
            f"🪪 *Member ID:* `{m.get('member_id')}`",
            "└─────────────────────┘",
            "",
        ]

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕒 *Timestamp:* {data.get('timestamp', 'N/A')}",
        f"💠 *Credit:* {data.get('credit', YOUR_CREDIT)}",
        f"✦ *Developer:* {data.get('developer', DEVELOPER)}",
    ]
    return "\n".join(lines)


# ============================================================
#                          ROUTES
# ============================================================

@app.get("/lookup")
async def lookup(number: str = Query(..., description="10-digit mobile number")):
    number = number.strip().replace("+91", "").replace(" ", "")
    if not number.isdigit() or len(number) != 10:
        raise HTTPException(400, detail={
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "message": "Invalid number. Sirf 10 digits, without +91.",
        })
    raw = await call_number_upstream(number)
    return JSONResponse(content=build_number_response(number, raw))


@app.get("/lookup/pretty", response_class=PlainTextResponse)
async def lookup_pretty(number: str = Query(..., description="10-digit mobile number")):
    number = number.strip().replace("+91", "").replace(" ", "")
    if not number.isdigit() or len(number) != 10:
        return "❌ Invalid number. Send 10-digit mobile number."
    raw = await call_number_upstream(number)
    return format_number_pretty(build_number_response(number, raw))


@app.get("/familyinfo")
async def familyinfo(aadhar: str = Query(..., description="12-digit Aadhaar number")):
    aadhar = aadhar.strip().replace(" ", "").replace("-", "")
    if not aadhar.isdigit() or len(aadhar) != 12:
        raise HTTPException(400, detail={
            "success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
            "message": "Invalid Aadhaar. Sirf 12 digits.",
        })
    raw = await call_family_upstream(aadhar)
    return JSONResponse(content=build_family_response(aadhar, raw))


@app.get("/familyinfo/pretty", response_class=PlainTextResponse)
async def familyinfo_pretty(aadhar: str = Query(..., description="12-digit Aadhaar number")):
    aadhar = aadhar.strip().replace(" ", "").replace("-", "")
    if not aadhar.isdigit() or len(aadhar) != 12:
        return "❌ Invalid Aadhaar. Send 12-digit number."
    raw = await call_family_upstream(aadhar)
    return format_family_pretty(build_family_response(aadhar, raw))


@app.get("/")
async def index():
    return {
        "name": "Info Lookup API",
        "version": "5.0.0",
        "credit": YOUR_CREDIT,
        "developer": DEVELOPER,
        "endpoints": {
            "/lookup?number=<10digit>": "Mobile → JSON",
            "/lookup/pretty?number=<10digit>": "Mobile → emoji text",
            "/familyinfo?aadhar=<12digit>": "Aadhaar → family JSON",
            "/familyinfo/pretty?aadhar=<12digit>": "Aadhaar → emoji text",
            "/docs": "Swagger UI",
            "/health": "Status check",
        },
        "examples": {
            "mobile": "/lookup?number=7355194378",
            "family": "/familyinfo?aadhar=123456789012",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "credit": YOUR_CREDIT, "developer": DEVELOPER}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
