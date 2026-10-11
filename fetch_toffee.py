#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Toffee IPTV Playlist Generator (Official Direct API + Paid Subscriber Token Engine)
-----------------------------------------------------------------------------------
Toffee-র সব লাইভ চ্যানেল (ফ্রি এবং পেইড প্রিমিয়াম যেমন Zee Bangla, Sony Sports, ইত্যাদি) 
স্বয়ংক্রিয়ভাবে সংগ্রহ করে VLC ও অন্যান্য IPTV প্লেয়ারের জন্য সম্পূর্ণ কার্যক্ষম M3U ফাইল তৈরি করে।

মূল বৈশিষ্ট্য:
  1) সম্পূর্ণ অটোমেটিক: আলাদা কোনো ম্যানুয়াল লগইন বা ক্যাপচা ছাড়াই সাইন্ড টোকেন সংগ্রহ করে।
  2) পেইড প্রিমিয়াম আনলক: অটো-আপডেটেড পেইড সাবস্ক্রিপশন টোকেন (subscriber_id) ব্যবহার করে
     সবগুলো প্রিমিয়াম চ্যানেল (Sony, Zee, Sports, Cartoon) VLC-তে সরাসরি প্লে করে।
  3) নিজস্ব অ্যাকাউন্টের সাপোর্ট: ব্যবহারকারীর নিজস্ব পেইড টোকেন থাকলে .env এর TOFFEE_TOKEN থেকেও কাজ করবে।
  4) ক্লিন প্লেলিস্ট: কোনো চ্যানেলের নামের পাশে [Premium] বা ফালতু ট্যাগ থাকবে না।
"""
import os
import sys
import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

# .env ফাইল সাপোর্ট (যদি থাকে)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# কনফিগারেশন
# ---------------------------------------------------------------------------
LOG_LEVEL = logging.INFO
OUTPUT_FILE = Path("toffee.m3u")

TOFFEE_BASE = "https://toffeelive.com"
TOFFEE_CONTENT_BASE = "https://content-prod.services.toffeelive.com/toffee/BD/DK/web/"
TOFFEE_PLAYBACK_BASE = "https://entitlement-prod.services.toffeelive.com/toffee/BD/DK/web/playback/"
TOFFEE_CDN_BASE = "https://prod-linear-media.toffeelive.com/cdn/live/"

# অটো-আপডেটেড সাবস্ক্রাইবার টোকেন মিরর সোর্স
MIRROR_DATA_URLS = [
    "https://raw.githubusercontent.com/sm-monirulislam/Toffee-Auto-Update/main/toffee_data.json",
    "https://raw.githubusercontent.com/Jeshan-akand/Toffee-Channels-Link-Headers/main/toffee_channel_data.json",
]

BASE_HEADERS = {
    "User-Agent": "okhttp/5.1.0",
    "Origin": "https://toffeelive.com",
    "Referer": "https://toffeelive.com/",
    "Accept": "application/json, text/plain, */*",
}

# ---------------------------------------------------------------------------
# Toffee বহির্ভূত অতিরিক্ত এক্সটেন্ডেড চ্যানেল (Star & Colors নেটওয়ার্ক)
# যা Toffee-র নিজস্ব সার্ভারে না থাকায় লাইভ ক্লাউড ও BDIX নোড থেকে যুক্ত করা হয়েছে
# ---------------------------------------------------------------------------
EXTENDED_CHANNELS = [
    {
        "name": "Star Jalsha HD",
        "category": "Bangla Entertainment",
        "logo": "https://i.imgur.com/IlufzR5.png",
        "link": "https://da86m1sqpm3o0.cloudfront.net/28072023/smil:starjalsha.smil/chunklist_b1928000.m3u8",
    },
    {
        "name": "Colors Bangla",
        "category": "Bangla Entertainment",
        "logo": "https://xstreamcp-assets-msp.streamready.in/assets/LIVETV/LIVECHANNEL/LIVETV_LIVETVCHANNEL_COLORS_BANGLA/images/LOGO_HD/image.png",
        "link": "http://103.114.11.37:8081/Colors-bangla/index.m3u8",
    },
    {
        "name": "Colors Bangla Cinema",
        "category": "Movie Channels",
        "logo": "https://xstreamcp-assets-msp.streamready.in/assets/LIVETV/LIVECHANNEL/LIVETV_LIVETVCHANNEL_COLORS_BANGLA_CINEMA/images/LOGO_HD/image.png",
        "link": "http://103.114.11.37:8081/Colors-bangla-cinema/index.m3u8",
    },
    {
        "name": "Enterr10 Bangla",
        "category": "Bangla Entertainment",
        "logo": "https://raw.githubusercontent.com/saeidrahmanbd/BDIX-IPTV/main/logos/enterr10-bangla.png",
        "link": "https://amg01448-samsungin-enterr10bangla-samsungin-ad-gg.amagi.tv/playlist/amg01448-samsungin-enterr10bangla-samsungin/playlist.m3u8",
    },
    {
        "name": "Star Gold HD",
        "category": "Movie Channels",
        "logo": "https://raw.githubusercontent.com/saeidrahmanbd/BDIX-IPTV/main/logos/star-gold.png",
        "link": "http://198.195.239.50:8095/STAR.GOLD.HD/index.m3u8",
    },
    {
        "name": "Zee Cinema HD",
        "category": "Movie Channels",
        "logo": "https://raw.githubusercontent.com/saeidrahmanbd/BDIX-IPTV/main/logos/zee-cinema.png",
        "link": "https://da86m1sqpm3o0.cloudfront.net/28072023/smil:zeecinemaapachd.smil/chunklist_b2628000.m3u8",
    },
]

# ---------------------------------------------------------------------------
# লগিং সেটআপ
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("toffee_generator")


def clean_text(s: str) -> str:
    """কী বা নাম সার্চ করার জন্য স্ট্রিং ক্লিন করে"""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def format_category(cat: str) -> str:
    """ক্যাটাগরিকে সুন্দর ইমোজি সহ সুসংগঠিত করে"""
    c = (cat or "").strip().lower()
    if "bangla ent" in c:
        return "🇧🇩 Bangla Entertainment"
    elif "hindi ent" in c:
        return "🎭 Hindi Entertainment"
    elif "hollywood" in c or "english mov" in c:
        return "🍿 Hollywood Movies"
    elif "movie" in c or "cinema" in c:
        return "🎬 Movies & Cinema"
    elif "sports" in c or "sport" in c:
        return "⚽ Sports HD"
    elif "news" in c:
        return "📰 Bangla News"
    elif "kids" in c or "cartoon" in c or "animation" in c:
        return "👶 Kids & Cartoons"
    elif "music" in c:
        return "🎶 Music Channels"
    elif "info" in c or "doc" in c or "geographic" in c or "planet" in c:
        return "🌍 Infotainment & Discovery"
    elif "relig" in c or "islam" in c or "devo" in c:
        return "🕋 Religious & Islamic"
    elif "ent" in c:
        return "📺 Entertainment"
    return cat or "📺 Other Channels"


# ---------------------------------------------------------------------------
# পেইড সাবস্ক্রিপশন মিরর ডেটা ফেচ
# ---------------------------------------------------------------------------
def fetch_paid_subscriber_pool() -> Dict[str, Dict[str, Any]]:
    """
    পেইড সাবস্ক্রাইবার টোকেন (subscriber_id) সহ লাইভ চ্যানেল পুল সংগ্রহ করে।
    """
    logger.info("পেইড সাবস্ক্রাইবার টোকেন পুল সংগ্রহ করা হচ্ছে...")
    for url in MIRROR_DATA_URLS:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code == 200:
                data = r.json()
                items = data.get("response") or data.get("channels") or []
                if items:
                    token_map = {}
                    for item in items:
                        name = item.get("name", "").strip()
                        link = item.get("link", "").strip()
                        logo = item.get("logo", "").strip()
                        cat = item.get("category_name") or item.get("category") or "Live TV"
                        if not link or "edge-cache-token" not in link:
                            continue

                        entry = {
                            "name": name,
                            "link": link,
                            "logo": logo,
                            "category": cat,
                        }

                        # বিভিন্ন কী দিয়ে ইনডেক্সিং যাতে মিস না হয়
                        k_name = clean_text(name)
                        token_map[k_name] = entry

                        m = re.search(r"/(?:live|cdn/live)/([^/]+)/", link)
                        if m:
                            slug_key = clean_text(m.group(1))
                            token_map[slug_key] = entry

                    logger.info(f"সফলভাবে {len(items)} টি চ্যানেলের পেইড সাবস্ক্রাইবার টোকেন লোড হয়েছে!")
                    return token_map
        except Exception as e:
            logger.warning(f"টোকেন পুল লোড করতে ব্যর্থ ({url}): {e}")

    logger.warning("পেইড সাবস্ক্রাইবার টোকেন মিরর পাওয়া যায়নি।")
    return {}


# ---------------------------------------------------------------------------
# অটোমেটিক সেশন ও কুকি ক্যাপচার
# ---------------------------------------------------------------------------
def get_or_capture_session() -> Dict[str, Any]:
    """
    সরাসরি toffeelive.com থেকে অফিসিয়াল সেশন ও ডিভাইস টোকেন ক্যাপচার করে।
    """
    custom_token = os.environ.get("TOFFEE_TOKEN", "").strip()
    custom_cookie = os.environ.get("TOFFEE_COOKIE", "").strip()

    if custom_cookie.startswith("Bearer "):
        custom_token = custom_cookie.replace("Bearer ", "").strip()
        custom_cookie = ""

    session = requests.Session()
    session.headers.update(BASE_HEADERS)

    if custom_token:
        logger.info("কাস্টম সাবস্ক্রাইবার টোকেন লোড হয়েছে (.env থেকে)।")
        return {
            "session": session,
            "token": custom_token,
            "cookie": custom_cookie,
            "is_custom": True,
        }

    logger.info("Toffee থেকে স্বয়ংক্রিয়ভাবে সেশন ক্যাপচার করা হচ্ছে...")
    try:
        session.get(TOFFEE_BASE, timeout=12)
        cookies = session.cookies.get_dict()
        device_token = cookies.get("device_token")
        if device_token:
            logger.info("অফিসিয়াল Device Token ক্যাপচার সম্পন্ন!")
            return {
                "session": session,
                "token": device_token,
                "cookie": "; ".join([f"{k}={v}" for k, v in cookies.items()]),
                "is_custom": False,
            }
    except Exception as e:
        logger.warning(f"সেশন ক্যাপচার সতর্কতা: {e}")

    return {
        "session": session,
        "token": "",
        "cookie": custom_cookie,
        "is_custom": False,
    }


# ---------------------------------------------------------------------------
# অফিশিয়াল চ্যানেল তালিকা সংগ্রহ
# ---------------------------------------------------------------------------
def fetch_all_official_channels(session: requests.Session) -> List[Dict[str, Any]]:
    """Toffee Content API থেকে সব অনন্য লাইভ চ্যানেল সংগ্রহ করে"""
    logger.info("Toffee Content API থেকে চ্যানেল তালিকা সংগ্রহ করা হচ্ছে...")
    view_url = f"{TOFFEE_CONTENT_BASE}view/live"

    try:
        r = session.get(view_url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"চ্যানেল ক্যাটাগরি লোড করতে ব্যর্থ: {e}")
        return []

    rails = data.get("rails", {}).get("list", [])
    channels_map = {}

    for rail in rails:
        cat_name = rail.get("title") or "Live TV"
        # Featured বা স্পন্সরড ড্রামা/শো হাইলাইট রেল বাদ দিন (যেমন "Didi No 1 | Zee Bangla")
        if "featured" in cat_name.lower():
            continue

        api_path = rail.get("apiPath")
        if not api_path:
            continue

        rail_url = f"{TOFFEE_CONTENT_BASE}{api_path}"
        try:
            res = session.get(rail_url, timeout=12)
            if res.status_code != 200:
                continue
            for item in res.json().get("list", []):
                cid = item.get("id")
                if not cid or cid in channels_map:
                    continue

                title = item.get("title") or item.get("name") or "Unknown"
                
                # ফেক বা প্রমোশনাল প্যাকেজ ফিল্টার (যেমন "179 TK Entertainment Pass")
                if any(x in title.lower() for x in ["pass", "pack", "subscription", "recharge"]):
                    continue

                media_list = item.get("media", [])
                media_id = media_list[0].get("mediaId") if media_list else None
                slug = item.get("slug") or item.get("streamSlug")

                if not slug and media_id:
                    slug = re.sub(r"[^a-z0-9_]", "", str(media_id).lower().replace("-", "_"))
                if not slug and cid:
                    slug = re.sub(r"[^a-z0-9_]", "", str(cid).lower().replace("-", "_"))

                logo = ""
                images = item.get("images", [])
                for img in images:
                    if img.get("ratio") == "1:1" and img.get("path"):
                        logo = f"https://assets-prod.services.toffeelive.com/{img['path']}"
                        break
                if not logo and images:
                    logo = f"https://assets-prod.services.toffeelive.com/{images[0].get('path', '')}"

                channels_map[cid] = {
                    "id": cid,
                    "title": title,
                    "media_id": media_id or cid,
                    "slug": slug or "",
                    "group": cat_name,
                    "logo": logo,
                    "is_premium": item.get("is_premium", False),
                }
        except Exception:
            pass

    channels = list(channels_map.values())
    logger.info(f"মোট {len(channels)} টি অফিশিয়াল চ্যানেল পাওয়া গেছে।")
    return channels


# ---------------------------------------------------------------------------
# প্লেব্যাক স্ট্রিম সমাধান (ডিরেক্ট + পেইড সাবস্ক্রাইবার ফলব্যাক)
# ---------------------------------------------------------------------------
def resolve_channel_stream(
    channel: Dict[str, Any],
    session_info: Dict[str, Any],
    paid_tokens: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """
    ১. ব্যবহারকারীর কাস্টম টোকেন থাকলে সরাসরি অফিসিয়াল Entitlement API থেকে স্ট্রিম নেয়।
    ২. গেস্ট টোকেনে অনুমতি মিললে ডিরেক্ট স্ট্রিম নেয়।
    ৩. প্রিমিয়াম চ্যানেল হলে পেইড সাবস্ক্রাইবার টোকেন পুল থেকে আনলকড স্ট্রিম সংগ্রহ করে।
    """
    session = session_info["session"]
    token = session_info["token"]
    cid = channel["id"]
    slug = channel.get("slug", "")
    title = channel.get("title", "")

    # কাস্টম সাবস্ক্রাইবার টোকেন থাকলে সরাসরি চেষ্টা করুন
    if session_info.get("is_custom") and token:
        try:
            playback_url = f"{TOFFEE_PLAYBACK_BASE}{cid}"
            res = session.post(
                playback_url,
                headers={"Authorization": f"Bearer {token}"},
                json={},
                timeout=8,
            )
            if res.status_code == 200:
                p_data = res.json()
                if p_data.get("access") == "allow":
                    data_list = p_data.get("playbackDetails", {}).get("data", [])
                    if data_list and isinstance(data_list, list):
                        url = data_list[0].get("url")
                        if url:
                            return url
        except Exception:
            pass

    # অফিসিয়াল ফ্রি চ্যানেল কিনা ডিরেক্ট টেস্ট
    if token and not session_info.get("is_custom"):
        try:
            playback_url = f"{TOFFEE_PLAYBACK_BASE}{cid}"
            res = session.post(
                playback_url,
                headers={"Authorization": f"Bearer {token}"},
                json={},
                timeout=6,
            )
            if res.status_code == 200:
                p_data = res.json()
                if p_data.get("access") == "allow":
                    data_list = p_data.get("playbackDetails", {}).get("data", [])
                    if data_list and isinstance(data_list, list):
                        url = data_list[0].get("url")
                        if url:
                            return url
        except Exception:
            pass

    # পেইড সাবস্ক্রাইবার পুল থেকে আনলকড টোকেন ম্যাচিং
    k_slug = clean_text(slug)
    k_title = clean_text(title)
    k_media = clean_text(channel.get("media_id", ""))

    matched = (
        paid_tokens.get(k_slug)
        or paid_tokens.get(k_title)
        or paid_tokens.get(k_media)
    )

    if matched and matched.get("link"):
        return matched["link"]

    # আংশিক নাম ম্যাচিং (যদি টাইটেলে পার্থক্য থাকে, যেমন Zee Bangla HD বনাম Zee Bangla)
    for k, v in paid_tokens.items():
        if k in k_title or k_title in k:
            if v.get("link"):
                return v["link"]

    return None


# ---------------------------------------------------------------------------
# M3U প্লেলিস্ট জেনারেশন
# ---------------------------------------------------------------------------
def build_m3u(
    channels: List[Dict[str, Any]],
    session_info: Dict[str, Any],
    paid_tokens: Dict[str, Dict[str, Any]],
) -> str:
    """স্ট্যান্ডার্ড ও ক্লিন M3U প্লেলিস্ট তৈরি করে"""
    ua_str = "okhttp/5.1.0"

    lines = [
        '#EXTM3U url-tvg="https://avkb.short.gy/tsepg.xml.gz"',
        "#===================================================",
        "# Toffee Live IPTV Playlist (Full All Channels)",
        "# Status: Free + Premium All Unlocked for VLC",
        "# Powered by Official Direct Engine & Paid Subscriber Tokens",
        "# Compatible: VLC Player, TiviMate, OTT Navigator",
        "#===================================================",
        "",
    ]

    working_count = 0
    added_titles = set()
    added_streams = set()

    # ১) অফিশিয়াল চ্যানেলগুলোর সমাধান
    for ch in channels:
        title = ch["title"].strip()
        logo = ch["logo"]
        group = ch["group"]
        media_id = ch["media_id"]

        stream_url = resolve_channel_stream(ch, session_info, paid_tokens)
        if not stream_url:
            continue

        stream_base = stream_url.split("?")[0].lower()
        k_title = clean_text(title)
        if k_title in added_titles or stream_base in added_streams:
            continue

        working_count += 1
        added_titles.add(k_title)
        added_streams.add(stream_base)

        grp_str = format_category(group)
        lines.append(
            f'#EXTINF:-1 tvg-id="{media_id}" tvg-chno="{working_count}" tvg-name="{title}" '
            f'tvg-logo="{logo}" group-title="{grp_str}",{title}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={ua_str}")
        lines.append("#EXTVLCOPT:http-reconnect=true")
        lines.append("#EXTVLCOPT:network-caching=6000")
        lines.append("#EXTVLCOPT:live-caching=6000")
        lines.append(f'#EXTHTTP:{{"user-agent":"{ua_str}"}}')
        lines.append(stream_url)
        lines.append("")

    # ২) পেইড পুলের অতিরিক্ত কোনো চ্যানেল থাকলে তা যুক্ত করা (যেন কোনো চ্যানেলই বাদ না পড়ে)
    for k, item in paid_tokens.items():
        name = item.get("name", "").strip()
        k_name = clean_text(name)
        link = item.get("link", "").strip()
        stream_base = link.split("?")[0].lower()
        if k_name in added_titles or stream_base in added_streams:
            continue

        logo = item.get("logo", "").strip()
        group = item.get("category", "Entertainment")

        if link:
            added_titles.add(k_name)
            added_streams.add(stream_base)
            working_count += 1
            grp_str = format_category(group)
            lines.append(
                f'#EXTINF:-1 tvg-id="{k_name}" tvg-chno="{working_count}" tvg-name="{name}" '
                f'tvg-logo="{logo}" group-title="{grp_str}",{name}'
            )
            lines.append(f"#EXTVLCOPT:http-user-agent={ua_str}")
            lines.append("#EXTVLCOPT:http-reconnect=true")
            lines.append("#EXTVLCOPT:network-caching=6000")
            lines.append("#EXTVLCOPT:live-caching=6000")
            lines.append(f'#EXTHTTP:{{"user-agent":"{ua_str}"}}')
            lines.append(link)
            lines.append("")

    # ৩) Toffee বহির্ভূত অতিরিক্ত এক্সটেন্ডেড চ্যানেল (Star Jalsha, Colors Bangla ইত্যাদি)
    for extra in EXTENDED_CHANNELS:
        name = extra["name"]
        k_name = clean_text(name)
        link = extra["link"]
        stream_base = link.split("?")[0].lower()
        if k_name in added_titles or stream_base in added_streams:
            continue

        logo = extra["logo"]
        group = extra["category"]
        added_titles.add(k_name)
        added_streams.add(stream_base)
        working_count += 1
        grp_str = format_category(group)
        lines.append(
            f'#EXTINF:-1 tvg-id="{k_name}" tvg-chno="{working_count}" tvg-name="{name}" '
            f'tvg-logo="{logo}" group-title="{grp_str}",{name}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={ua_str}")
        lines.append("#EXTVLCOPT:http-reconnect=true")
        cache_ms = 10000 if "gold" in k_name or "star" in k_name else 6000
        lines.append(f"#EXTVLCOPT:network-caching={cache_ms}")
        lines.append(f"#EXTVLCOPT:live-caching={cache_ms}")
        lines.append(f'#EXTHTTP:{{"user-agent":"{ua_str}"}}')
        lines.append(link)
        lines.append("")

    logger.info(f"প্লেলিস্ট তৈরি সম্পন্ন: মোট {working_count} টি কার্যকর লাইভ চ্যানেল অন্তর্ভুক্ত হয়েছে!")
    return "\n".join(lines)


def write_m3u_safely(content: str, output_path: Path) -> bool:
    """ফাইল নিরাপদে সেভ করে"""
    tmp_path = output_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        tmp_path.replace(output_path)
        logger.info(f"প্লেলিস্ট ফাইল আপডেট হয়েছে: {output_path} ({len(content)} bytes)")
        return True
    except Exception as e:
        logger.exception(f"ফাইল সংরক্ষণে ত্রুটি: {e}")
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        return False


# ---------------------------------------------------------------------------
# মূল ফাংশন
# ---------------------------------------------------------------------------
def main() -> int:
    """মূল এক্সিকিউশন পাইপলাইন"""
    logger.info("=== Toffee IPTV Generator শুরু হচ্ছে ===")

    # ১) পেইড সাবস্ক্রাইবার পুল লোড
    paid_tokens = fetch_paid_subscriber_pool()

    # ২) অফিসিয়াল সেশন ও টোকেন ক্যাপচার
    session_info = get_or_capture_session()

    # ৩) অফিশিয়াল চ্যানেল সংগ্রহ
    channels = fetch_all_official_channels(session_info["session"])

    # ৪) প্লেলিস্ট তৈরি
    m3u_content = build_m3u(channels, session_info, paid_tokens)

    # ৫) M3U ফাইল রাইট
    if not write_m3u_safely(m3u_content, OUTPUT_FILE):
        return 1

    logger.info("=== সম্পূর্ণ প্রক্রিয়া সফল হয়েছে! ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())