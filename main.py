# language: Python, file: main.py, target: Railway / any Linux, Python 3.9+
# *FastAPI wrapper — Num Info Lookup + Aadhaar Family Info*

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import uvicorn

app = FastAPI(
    title="Info Lookup API",
    description="Mobile number + Aadhaar family info",
    version="6.0.0",
)

# ---------- Config ----------
NUMBER_API_URL = "https://api.naxupdate.workers.dev/api/number-info"
NUMBER_API_KEY = "30Day"

# NAYA FAMILY API — Dark API Hub
FAMILY_API_URL = "https://dark-api-hub.onrender.com/api/adharfamily"
FAMILY_API_KEY = "DEMO"

YOUR_CREDIT = "@YoBlackX"
DEVELOPER = "YoBlackX"
REQUEST_TIMEOUT = 40
MAX_RECORDS = 5


# ============================================================
#                     NUMBER INFO SECTION (unchanged)
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
    seen, out = set(), []
    for r in records:
        key = (r.get("name"), r.get("mobile"), r.get("Aadhar"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_number_response(number: str, raw: dict) -> dict:
    if "_error" in raw:
        return {"success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
                "query": number, "message": raw["_error"]}
    if not raw.get("success", False):
        return {"success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
                "query": number, "message": raw.get("message", "No data found")}

    data_node = raw.get("data") or {}
    if not isinstance(data_node, dict) or not data_node.get("found", False):
        return {"success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
                "query": number, "message": data_node.get("message", "No data found")}

    records = data_node.get("result", []) or []
    if not isinstance(records, list):
        records = []

    cleaned = [clean_record(r) for r in records]
    cleaned = [r for r in cleaned if r]
    cleaned = dedupe_records(cleaned)[:MAX_RECORDS]

    key_info = raw.get("key") or {}
    return {
        "success": True, "credit": YOUR_CREDIT, "developer": DEVELOPER,
        "query": number, "total_records": len(cleaned), "data": cleaned,
        "usage": {
            "daily_remaining": key_info.get("dailyRemaining", "N/A"),
            "max_remaining": key_info.get("maxRemaining", "N/A"),
        },
    }


def format_number_pretty(data: dict) -> str:
    if not data.get("success"):
        return (f"❌ *Lookup Failed*\n━━━━━━━━━━━━━━━━━━━━\n"
                f"🔍 *Query:* `{data.get('query', 'N/A')}`\n"
                f"⚠️ *Message:* {data.get('message', 'Unknown error')}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n💠 *Credit:* {data.get('credit', YOUR_CREDIT)}")

    records = data.get("data", [])
    usage = data.get("usage", {}) or {}
    lines = ["📱 *NUM INFO LOOKUP*", "━━━━━━━━━━━━━━━━━━━━",
             f"🔍 *Query:* `{data.get('query')}`",
             f"📊 *Records:* {data.get('total_records', 0)}", ""]
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
    lines += ["━━━━━━━━━━━━━━━━━━━━",
              f"📊 *Daily Left:* {usage.get('daily_remaining', 'N/A')}",
              f"💠 *Credit:* {data.get('credit', YOUR_CREDIT)}"]
    return "\n".join(lines)


# ============================================================
#                     FAMILY INFO SECTION (NEW API)
# ============================================================

async def call_family_upstream(aadhar: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(
                FAMILY_API_URL,
                params={"key": FAMILY_API_KEY, "num": aadhar},
            )
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return {"_error": "Upstream timeout. Dobara try karo."}
    except httpx.HTTPError as e:
        return {"_error": f"Upstream request failed: {str(e)}"}
    except ValueError:
        return {"_error": "Upstream ne invalid JSON bheja"}


REL_EMOJI = {
    "SELF": "🙋", "FATHER": "👨", "MOTHER": "👩",
    "HUSBAND": "👨", "WIFE": "👩", "SON": "👦", "DAUGHTER": "👧",
    "BROTHER": "👨", "SISTER": "👩", "OTHER": "👤",
}


def _first(d: dict, *keys, default="N/A"):
    """Helper: pehla non-empty key value return karo"""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", 0):
            return v
    return default


def _extract_members(raw: dict) -> list:
    """
    Different possible structures me se member list nikaalo:
      1. raw["data"]["ALL-DETAILS"]["memberDetailsList"]  (purana dark-info)
      2. raw["data"]["members"] / memberList / result
      3. raw["data"] (list directly)
      4. raw["members"] / raw["result"]
      5. raw (agar root list hai to — caller handle karta hai)
    """
    if not isinstance(raw, dict):
        return []

    # path 1: nested ALL-DETAILS
    dn = raw.get("data")
    if isinstance(dn, dict):
        for ck in ("ALL-DETAILS", "allDetails", "all_details"):
            cd = dn.get(ck)
            if isinstance(cd, dict):
                for mk in ("memberDetailsList", "members", "memberList", "result"):
                    mv = cd.get(mk)
                    if isinstance(mv, list):
                        return mv
        # path 2: direct members under data
        for mk in ("members", "memberList", "memberDetailsList", "result", "records"):
            mv = dn.get(mk)
            if isinstance(mv, list):
                return mv

    # path 3: data is a list
    if isinstance(dn, list):
        return dn

    # path 4: top-level members
    for mk in ("members", "memberList", "result", "records", "data"):
        mv = raw.get(mk)
        if isinstance(mv, list):
            return mv

    return []


def _extract_ration_card(raw: dict) -> dict:
    """Ration card details nikaalo (nested ya flat)"""
    dn = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(dn, dict):
        for ck in ("ALL-DETAILS", "allDetails", "all_details"):
            cd = dn.get(ck)
            if isinstance(cd, dict):
                return cd
        return dn
    return raw if isinstance(raw, dict) else {}


def clean_family_member(m: dict) -> dict:
    if not isinstance(m, dict):
        return {}
    rel = _first(m, "releationship_name", "relationship_name", "relationship",
                 "relation", default="N/A")
    return {
        "name": _first(m, "memberName", "member_name", "name"),
        "relationship": str(rel).upper(),
        "masked_aadhar": _first(m, "maskedUid", "masked_aadhar", "aadhaar", "uid"),
        "member_id": _first(m, "memberId", "member_id", "id"),
        "has_uid": _first(m, "uid", "has_uid"),
    }


def build_family_response(aadhar: str, raw) -> dict:
    # Error
    if isinstance(raw, dict) and "_error" in raw:
        return {"success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
                "query": aadhar, "message": raw["_error"]}

    # Failure status check (multiple possible flag names)
    if isinstance(raw, dict):
        status_val = str(_first(raw, "status", "success", "ok", default="")).lower()
        if status_val in ("false", "failed", "error", "0"):
            msg = _first(raw, "M-S-G", "message", "msg", "error", default="No data found")
            return {"success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
                    "query": aadhar, "message": msg}

    # Member list nikaalo
    if isinstance(raw, list):
        members_raw = raw
    else:
        members_raw = _extract_members(raw)

    if not members_raw:
        msg = "No family details found"
        if isinstance(raw, dict):
            msg = _first(raw, "M-S-G", "message", "msg",
                         "N-A", default=msg)
        return {"success": False, "credit": YOUR_CREDIT, "developer": DEVELOPER,
                "query": aadhar, "message": msg}

    members = [clean_family_member(m) for m in members_raw]
    members = [m for m in members if m]
    members.sort(key=lambda x: (0 if x["relationship"] == "SELF" else 1, x["name"]))

    # Ration card block
    rc_raw = _extract_ration_card(raw) if isinstance(raw, dict) else {}
    ration_card = {
        "rc_id": _first(rc_raw, "rcId", "rc_id", "ration_card_id"),
        "scheme": _first(rc_raw, "schemeName", "scheme_name", "scheme"),
        "fps_id": _first(rc_raw, "fpsId", "fps_id"),
        "address": _first(rc_raw, "address", "addr"),
        "district": _first(rc_raw, "homeDistName", "district", "dist_name"),
        "state": _first(rc_raw, "homeStateName", "state", "state_name"),
        "onorc_allowed": _first(rc_raw, "allowed_onorc", "onorc", "onorc_allowed"),
    }

    ts = _first(raw, "timestamp", "time", "fetched_at") if isinstance(raw, dict) else "N/A"

    return {
        "success": True, "credit": YOUR_CREDIT, "developer": DEVELOPER,
        "query": aadhar, "total_members": len(members),
        "ration_card": ration_card, "members": members, "timestamp": ts,
    }


def format_family_pretty(data: dict) -> str:
    if not data.get("success"):
        return (f"❌ *Family Lookup Failed*\n━━━━━━━━━━━━━━━━━━━━\n"
                f"🔍 *Aadhaar:* `{data.get('query', 'N/A')}`\n"
                f"⚠️ *Message:* {data.get('message', 'Unknown error')}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n💠 *Credit:* {data.get('credit', YOUR_CREDIT)}")

    rc = data.get("ration_card", {}) or {}
    members = data.get("members", [])

    lines = [
        "👨‍👩‍👧‍👦 *FAMILY INFO LOOKUP*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔍 *Aadhaar:* `{data.get('query')}`",
        f"👥 *Members:* {data.get('total_members', 0)}",
        "",
    ]

    # Sirf tab dikhao jab ration card data ho
    if any(rc.get(k) not in (None, "", "N/A") for k in
           ("rc_id", "scheme", "fps_id", "address", "district", "state")):
        lines += [
            "🏠 *RATION CARD DETAILS*",
            f"🆔 *RC ID:* `{rc.get('rc_id')}`",
            f"📋 *Scheme:* {rc.get('scheme')}",
            f"🏪 *FPS ID:* `{rc.get('fps_id')}`",
            f"📍 *Address:* {str(rc.get('address'))[:120]}",
            f"🗺️ *District:* {rc.get('district')}",
            f"🏛️ *State:* {rc.get('state')}",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

    lines += ["👥 *FAMILY MEMBERS*", ""]

    for i, m in enumerate(members, 1):
        emoji = REL_EMOJI.get(m["relationship"], "👤")
        lines += [
            f"┌─── *MEMBER {i}* ───┐",
            f"{emoji} *Name:* {m.get('name')}",
            f"🔗 *Relation:* {m.get('relationship')}",
            f"🆔 *Masked Aadhaar:* `{m.get('masked_aadhar')}`",
            f"🪪 *Member ID:* `{m.get('member_id')}`",
            "└─────────────────────┘", "",
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
        "name": "Info Lookup API", "version": "6.0.0",
        "credit": YOUR_CREDIT, "developer": DEVELOPER,
        "endpoints": {
            "/lookup?number=<10digit>": "Mobile → JSON",
            "/lookup/pretty?number=<10digit>": "Mobile → emoji text",
            "/familyinfo?aadhar=<12digit>": "Aadhaar → family JSON",
            "/familyinfo/pretty?aadhar=<12digit>": "Aadhaar → emoji text",
            "/docs": "Swagger UI", "/health": "Status check",
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
