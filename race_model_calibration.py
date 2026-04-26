from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math
import re
import statistics

# =========================================================
# Race Model Calibration v1
# ---------------------------------------------------------
# Amaç:
# - Aday bulma motoru ile final sıralama motorunu ayırmak
# - Yarış tipi bazlı kalibrasyon yapmak
# - Tek süre yerine süre bandı üretmek
# - H2H / cross-H2H / galop / kilo / start / zemin taşıma / Maiden sıçrama
#   sinyallerini aynı iskelette toplamak
# =========================================================


# ----------------------------
# Temel yardımcı fonksiyonlar
# ----------------------------

def pace_to_seconds(time_str: str) -> Optional[float]:
    """
    '1.11.15' veya '2.01.47' gibi TJK formatını saniyeye çevirir.
    None veya boş ise None döner.
    """
    if not time_str:
        return None
    s = str(time_str).strip().replace("'", ".").replace('"', "")
    parts = s.split('.')
    try:
        if len(parts) == 3:
            minutes = int(parts[0])
            seconds = int(parts[1])
            hundredths = int(parts[2])
            return minutes * 60 + seconds + hundredths / 100.0
        if len(parts) == 2:
            return float(parts[0]) + float(parts[1]) / 100.0
        return float(s)
    except Exception:
        return None


def seconds_to_tjk(sec: float) -> str:
    m = int(sec // 60)
    s = sec - m * 60
    whole = int(s)
    hund = int(round((s - whole) * 100))
    if hund == 100:
        whole += 1
        hund = 0
    return f"{m}.{whole:02d}.{hund:02d}"


def kg_penalty_seconds(distance: int) -> float:
    if distance <= 900:
        return 0.02
    if distance <= 1200:
        return 0.03
    if distance <= 1400:
        return 0.05
    if distance <= 1600:
        return 0.05
    if distance <= 1700:
        return 0.06
    if distance <= 2000:
        return 0.08
    return 0.09


def going_penalty(going: str) -> float:
    m = {
        "Çok Ağır": 4.0,
        "Ağır": 2.5,
        "Yumuşak": 0.8,
        "Nemli": 1.2,
        "Islak": 1.5,
        "Sulu": 2.0,
        "Normal": 0.0,
        "": 0.0,
        None: 0.0,
    }
    return m.get(going, 0.0)


def band_of_distance(distance: int) -> str:
    if distance <= 1100:
        return "sprint"
    if distance <= 1300:
        return "short"
    if distance <= 1500:
        return "short_mid"
    if distance <= 1700:
        return "mid"
    if distance <= 2000:
        return "mid_long"
    return "stayer"


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    return default if not b else a / b


# ----------------------------
# Veri modelleri
# ----------------------------


@dataclass
class RaceRecord:
    date: str
    city: str
    surface: str
    distance: int
    going: str
    race_class: str
    position: Optional[int]
    time_sec: Optional[float]
    weight: Optional[float]
    jockey: Optional[str]
    hp: Optional[float]
    start_no: Optional[int]
    margin_desc: Optional[str] = None
    note: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RaceRecord":
        return RaceRecord(
            date=str(data.get("date", "")),
            city=str(data.get("city", "")),
            surface=str(data.get("surface", "")),
            distance=int(data.get("distance", 0)),
            going=str(data.get("going", "")),
            race_class=str(data.get("race_class", "")),
            position=data.get("position"),
            time_sec=data.get("time_sec"),
            weight=data.get("weight"),
            jockey=data.get("jockey"),
            hp=data.get("hp"),
            start_no=data.get("start_no"),
            margin_desc=data.get("margin_desc"),
            note=data.get("note"),
        )


@dataclass
class WorkoutRecord:
    date: str
    city: str
    d600: Optional[float] = None
    d400: Optional[float] = None
    d800: Optional[float] = None
    effort: Optional[str] = None
    inner_outer: Optional[str] = None
    jockey: Optional[str] = None
    weight: Optional[float] = None
    surface: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "WorkoutRecord":
        return WorkoutRecord(
            date=str(data.get("date", "")),
            city=str(data.get("city", "")),
            d600=data.get("d600"),
            d400=data.get("d400"),
            d800=data.get("d800"),
            effort=data.get("effort"),
            inner_outer=data.get("inner_outer"),
            jockey=data.get("jockey"),
            weight=data.get("weight"),
            surface=data.get("surface"),
        )


@dataclass
class Runner:
    no: int
    name: str
    age_group: str
    breed: str  # 'Arap' / 'İngiliz'
    sex: Optional[str]
    race_weight: float
    jockey: str
    trainer: Optional[str]
    start_no: Optional[int]
    hp: Optional[float]
    gp: Optional[float]
    agf: Optional[float]
    equipment: Optional[str]
    race_records: List[RaceRecord] = field(default_factory=list)
    workouts: List[WorkoutRecord] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Runner":
        race_records = [RaceRecord.from_dict(x) for x in data.get("race_records", [])]
        workouts = [WorkoutRecord.from_dict(x) for x in data.get("workouts", [])]
        return Runner(
            no=int(data["no"]),
            name=str(data["name"]),
            age_group=str(data.get("age_group", "")),
            breed=str(data.get("breed", "")),
            sex=data.get("sex"),
            race_weight=float(data.get("race_weight", 0.0)),
            jockey=str(data.get("jockey", "")),
            trainer=data.get("trainer"),
            start_no=data.get("start_no"),
            hp=data.get("hp"),
            gp=data.get("gp"),
            agf=data.get("agf"),
            equipment=data.get("equipment"),
            race_records=race_records,
            workouts=workouts,
        )


@dataclass
class RaceContext:
    city: str
    surface: str
    distance: int
    going: str
    breed: str
    age_group: str
    race_class: str
    eid_sec: Optional[float] = None
    is_maiden: bool = False

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RaceContext":
        return RaceContext(
            city=str(data.get("city", "")),
            surface=str(data.get("surface", "")),
            distance=int(data.get("distance", 0)),
            going=str(data.get("going", "")),
            breed=str(data.get("breed", "")),
            age_group=str(data.get("age_group", "")),
            race_class=str(data.get("race_class", "")),
            eid_sec=data.get("eid_sec"),
            is_maiden=bool(data.get("is_maiden", False)),
        )


# ----------------------------
# Yarış tipi ayarları
# ----------------------------

RACE_TYPE_WEIGHTS: Dict[str, Dict[str, float]] = {
    # 3 yaşlı İngiliz Maiden 1600 Kum
    "İngiliz|maiden|1600|Kum": {
        "recent_same_surface": 0.24,
        "distance_fit": 0.14,
        "second_start_bounce": 0.10,
        "workout": 0.18,
        "gate": 0.08,
        "weight": 0.08,
        "h2h": 0.06,
        "cross_h2h": 0.04,
        "class_strength": 0.04,
        "surface_transfer": 0.04,
        "form_momentum": 0.04,
    },
    # 3 yaşlı İngiliz Hnd kısa kum sprint
    "İngiliz|handicap|1200|Kum": {
        "recent_same_surface": 0.28,
        "distance_fit": 0.16,
        "workout": 0.18,
        "gate": 0.10,
        "weight": 0.14,
        "h2h": 0.04,
        "cross_h2h": 0.02,
        "class_strength": 0.04,
        "surface_transfer": 0.04,
        "form_momentum": 0.02,
    },
    # 4 yaşlı Arap ŞRT-5 1600 kum
    "Arap|sart|1600|Kum": {
        "recent_same_surface": 0.22,
        "distance_fit": 0.16,
        "workout": 0.16,
        "gate": 0.12,
        "weight": 0.12,
        "h2h": 0.08,
        "cross_h2h": 0.06,
        "class_strength": 0.04,
        "surface_transfer": 0.04,
        "form_momentum": 0.04,
    },
    # varsayılan
    "default": {
        "recent_same_surface": 0.22,
        "distance_fit": 0.15,
        "workout": 0.16,
        "gate": 0.10,
        "weight": 0.10,
        "h2h": 0.08,
        "cross_h2h": 0.06,
        "class_strength": 0.07,
        "surface_transfer": 0.06,
        "form_momentum": 0.06,
    },
}


# ----------------------------
# Zemin / şehir taşıma modülü
# ----------------------------

NORMAL_KUM_CITIES = {"Ankara", "Adana", "Bursa", "İzmir"}
DERE_KUMU_CITIES = {"Elazığ", "Şanlıurfa", "Diyarbakır"}
SENTETIK_CITIES = {"İstanbul", "Antalya"}


def city_surface_bucket(city: str, surface: str) -> str:
    if surface == "Kum":
        if city in DERE_KUMU_CITIES:
            return "dere_kumu"
        if city in NORMAL_KUM_CITIES:
            return "normal_kum"
    if surface == "Sentetik":
        return "sentetik"
    if surface == "Çim":
        return "cim"
    return f"{city}:{surface}"


def transfer_penalty(from_city: str, from_surface: str, to_city: str, to_surface: str) -> float:
    fb = city_surface_bucket(from_city, from_surface)
    tb = city_surface_bucket(to_city, to_surface)
    if fb == tb:
        if from_city == to_city:
            return 0.0
        return 0.5
    if {fb, tb} == {"normal_kum", "dere_kumu"}:
        return 2.5
    if {fb, tb} == {"normal_kum", "sentetik"}:
        return 2.0
    if fb == "cim" and tb == "Kum":
        return 2.0
    return 1.5


# ----------------------------
# Skor fonksiyonları
# ----------------------------


def recency_surface_score(runner: Runner, ctx: RaceContext) -> float:
    score = 0.0
    for rr in runner.race_records[:6]:
        if rr.surface == ctx.surface:
            score += 1.2
            if abs(rr.distance - ctx.distance) <= 100:
                score += 1.3
            elif abs(rr.distance - ctx.distance) <= 200:
                score += 0.7
            if rr.position is not None:
                if rr.position <= 3:
                    score += 1.2
                elif rr.position <= 5:
                    score += 0.5
    return score


def distance_fit_score(runner: Runner, ctx: RaceContext) -> float:
    wanted = band_of_distance(ctx.distance)
    s = 0.0
    for rr in runner.race_records[:8]:
        band = band_of_distance(rr.distance)
        if band == wanted:
            s += 1.0
        elif abs(rr.distance - ctx.distance) <= 200:
            s += 0.6
        if rr.position is not None and rr.position <= 3:
            s += 0.4
    return s


def second_start_bounce_score(runner: Runner, ctx: RaceContext) -> float:
    # Özellikle Maiden kısa koşularda kötü debut + iyi iş = sıçrama bonusu
    if not ctx.is_maiden:
        return 0.0
    if len(runner.race_records) != 1:
        return 0.0
    rr = runner.race_records[0]
    recent_work = workout_score(runner, ctx)
    poor_debut = 1.0 if (rr.position is not None and rr.position >= 5) else 0.0
    return poor_debut * recent_work * 0.7


def workout_score(runner: Runner, ctx: RaceContext) -> float:
    # Basit ama işe yarar galop skoru
    if not runner.workouts:
        return 0.0
    scores = []
    for w in runner.workouts[:5]:
        s = 0.0
        if w.city == ctx.city:
            s += 1.0
        if w.effort in {"Çalışarak", "Hafif Çalışarak"}:
            s += 0.5
        if ctx.distance <= 1100:
            if w.d400 is not None:
                if w.d400 <= 27.0:
                    s += 1.6
                elif w.d400 <= 28.0:
                    s += 1.0
                elif w.d400 <= 29.0:
                    s += 0.5
            if w.d600 is not None and w.d600 <= 42.5:
                s += 0.7
        elif ctx.distance <= 1600:
            if w.d600 is not None:
                if w.d600 <= 55.5:
                    s += 1.2
                elif w.d600 <= 57.0:
                    s += 0.8
            if w.d400 is not None and w.d400 <= 28.0:
                s += 0.5
        else:
            if w.d800 is not None and w.d800 <= 50.5:
                s += 0.8
            if w.d600 is not None and w.d600 <= 41.5:
                s += 0.5
        scores.append(s)
    return statistics.mean(scores)


def gate_score(runner: Runner, ctx: RaceContext, field_size: int) -> float:
    if runner.start_no is None:
        return 0.0
    st = runner.start_no
    if ctx.distance <= 1100:
        if st <= 4:
            return 1.0
        if st <= 8:
            return 0.4
        return -0.6
    if ctx.distance <= 1600:
        if st <= 4:
            return 0.7
        if st <= 8:
            return 0.3
        if st >= max(10, field_size - 1):
            return -0.5
    return 0.0


def weight_score(runner: Runner, ctx: RaceContext, field_weights: List[float]) -> float:
    avg_w = statistics.mean(field_weights)
    diff = avg_w - runner.race_weight
    coeff = 0.25 if ctx.distance <= 1200 else 0.18
    return diff * coeff


def class_strength_score(runner: Runner, ctx: RaceContext) -> float:
    s = 0.0
    for rr in runner.race_records[:5]:
        if rr.race_class:
            rc = rr.race_class.lower()
            if "kv" in rc or "g" in rc:
                s += 0.6
            elif "handikap" in rc or "han" in rc:
                s += 0.3
            elif "mai" in rc:
                s += 0.15
        if rr.position is not None and rr.position <= 3:
            s += 0.2
    return s


def form_momentum_score(runner: Runner, ctx: RaceContext) -> float:
    """
    Son koşu performansını (form) ivme olarak puanlar.
    En güncel koşular daha yüksek ağırlık alır.
    """
    if not runner.race_records:
        return 0.0

    momentum = 0.0
    for idx, rr in enumerate(runner.race_records[:6]):
        recency_w = max(0.35, 1.0 - idx * 0.12)
        comp = 0.0

        if rr.position is not None:
            if rr.position == 1:
                comp += 1.8
            elif rr.position <= 3:
                comp += 1.2
            elif rr.position <= 5:
                comp += 0.5
            else:
                comp -= 0.4

        if abs(rr.distance - ctx.distance) <= 100:
            comp += 0.45
        elif abs(rr.distance - ctx.distance) <= 200:
            comp += 0.20

        if rr.surface == ctx.surface:
            comp += 0.35

        if rr.time_sec is not None:
            # aynı mesafede kaba tempo bonusu
            speed = safe_div(rr.distance, rr.time_sec, default=0.0)
            if speed >= 16.8:
                comp += 0.35
            elif speed >= 16.3:
                comp += 0.20

        momentum += recency_w * comp

    return momentum


def surface_transfer_score(runner: Runner, ctx: RaceContext) -> float:
    if not runner.race_records:
        return 0.0
    rr = runner.race_records[0]
    penalty = transfer_penalty(rr.city, rr.surface, ctx.city, ctx.surface)
    return max(0.0, 2.0 - penalty)


def h2h_score(runner: Runner, all_runners: List[Runner], ctx: RaceContext) -> float:
    # Hafif bir placeholder. Aynı yarış günü geçmişte aynı rakipleri geçmişse puan verir.
    return 0.0


def cross_h2h_score(runner: Runner, all_runners: List[Runner], ctx: RaceContext) -> float:
    return 0.0


# ----------------------------
# Süre motoru
# ----------------------------


def normalize_race_time(rr: RaceRecord, runner: Runner, ctx: RaceContext) -> Optional[float]:
    if rr.time_sec is None:
        return None
    t = rr.time_sec
    # pist durumu düzeltmesi
    t -= going_penalty(rr.going)
    # HP düzeltmesi
    if rr.hp is not None and runner.hp is not None:
        hp_delta = runner.hp - rr.hp
        t -= (hp_delta / 5.0) * 0.35
    # kilo düzeltmesi
    if rr.weight is not None:
        t += (runner.race_weight - rr.weight) * kg_penalty_seconds(ctx.distance)
    # zemin/şehir taşıma cezası
    t += transfer_penalty(rr.city, rr.surface, ctx.city, ctx.surface)
    # mesafe dönüşümü
    ref_speed = rr.distance / t
    fatigue = max(0.0, (ctx.distance - rr.distance) / 100.0) * 0.45
    if rr.distance > ctx.distance:
        fatigue -= abs(ctx.distance - rr.distance) / 100.0 * 0.20
    pred = ctx.distance / ref_speed + max(fatigue, -1.5)
    return pred


def estimate_time_band(runner: Runner, ctx: RaceContext) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
    preds: List[float] = []
    for rr in runner.race_records[:5]:
        p = normalize_race_time(rr, runner, ctx)
        if p is not None:
            preds.append(p)

    if not preds and runner.workouts:
        # Galop fallback
        for w in runner.workouts[:3]:
            if ctx.distance <= 1100 and w.d400 is not None:
                # kaba sprint dönüşümü
                speed = 400.0 / w.d400
                race_speed = speed * 0.93
                preds.append(ctx.distance / race_speed)
            elif ctx.distance <= 1600 and w.d600 is not None:
                speed = 600.0 / w.d600
                race_speed = speed * 0.80
                preds.append(ctx.distance / race_speed)

    if not preds:
        return None, None

    preds.sort()
    core = preds[:3]
    center = statistics.median(core)
    lo = min(core) - 0.25
    hi = max(core) + 0.55
    return center, (lo, hi)


# ----------------------------
# Final model
# ----------------------------


def race_type_key(ctx: RaceContext) -> str:
    cls = "maiden" if ctx.is_maiden else ("handicap" if "han" in ctx.race_class.lower() else "sart")
    return f"{ctx.breed}|{cls}|{ctx.distance}|{ctx.surface}"


def get_weights(ctx: RaceContext) -> Dict[str, float]:
    return RACE_TYPE_WEIGHTS.get(race_type_key(ctx), RACE_TYPE_WEIGHTS["default"])


def score_runner(runner: Runner, all_runners: List[Runner], ctx: RaceContext) -> Dict[str, float]:
    weights = get_weights(ctx)
    field_weights = [r.race_weight for r in all_runners]

    parts = {
        "recent_same_surface": recency_surface_score(runner, ctx),
        "distance_fit": distance_fit_score(runner, ctx),
        "second_start_bounce": second_start_bounce_score(runner, ctx),
        "workout": workout_score(runner, ctx),
        "gate": gate_score(runner, ctx, len(all_runners)),
        "weight": weight_score(runner, ctx, field_weights),
        "h2h": h2h_score(runner, all_runners, ctx),
        "cross_h2h": cross_h2h_score(runner, all_runners, ctx),
        "class_strength": class_strength_score(runner, ctx),
        "surface_transfer": surface_transfer_score(runner, ctx),
        "form_momentum": form_momentum_score(runner, ctx),
    }

    total = 0.0
    for k, v in parts.items():
        total += weights.get(k, 0.0) * v
    parts["total"] = total
    return parts


def rank_runners(runners: List[Runner], ctx: RaceContext) -> List[Dict[str, Any]]:
    scored = []
    raw_scores = []
    for r in runners:
        score = score_runner(r, runners, ctx)
        time_center, time_band = estimate_time_band(r, ctx)
        item = {
            "no": r.no,
            "name": r.name,
            "score": score,
            "time_center": time_center,
            "time_band": time_band,
        }
        raw_scores.append(score["total"])
        scored.append(item)

    # göreli kazanma yüzdesi
    if raw_scores:
        exps = [math.exp(s) for s in raw_scores]
        denom = sum(exps)
        for item, e in zip(scored, exps):
            item["win_pct"] = 100.0 * e / denom
        scored.sort(key=lambda x: x["score"]["total"], reverse=True)
    return scored


# ----------------------------
# Basit backtest / calibration hook
# ----------------------------


def topk_hit_rate(pred_order: List[int], true_order: List[int], k: int = 5, target_top: int = 3) -> float:
    pred_set = set(pred_order[:k])
    true_set = set(true_order[:target_top])
    return len(pred_set & true_set) / float(target_top)


def score_diagnostics(pred_order: List[int], true_order: List[int]) -> Dict[str, Any]:
    return {
        "top5_contains_true_top3": topk_hit_rate(pred_order, true_order, k=5, target_top=3),
        "top3_exact_overlap": len(set(pred_order[:3]) & set(true_order[:3])),
        "winner_hit": int(pred_order[0] == true_order[0]),
    }


def run_race_case(
    race_context: Dict[str, Any],
    runners: List[Dict[str, Any]],
    true_order: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Dışarıdan gelen ham sözlüklerle tek yarış senaryosu çalıştırır.
    - race_context: yarış bağlamı
    - runners: at listesi
    - true_order: varsa gerçek bitiriş sırası (at no listesi)
    """
    ctx = RaceContext.from_dict(race_context)
    runner_objs = [Runner.from_dict(r) for r in runners]
    ranking = rank_runners(runner_objs, ctx)

    output: Dict[str, Any] = {"ranking": ranking}
    if true_order:
        pred_order = [x["no"] for x in ranking]
        output["diagnostics"] = score_diagnostics(pred_order, true_order)
    return output


def _parse_best_degree_token(token: str) -> Optional[Tuple[float, str, str]]:
    """
    Örnek: 57/1.20.82/NOR/ADA -> (80.82, "Normal", "Adana")
    """
    m = re.match(
        r"^\d+/(?P<t>\d+\.\d+\.\d+)(?:/(?P<going>[A-ZÇĞİÖŞÜ]+))?(?:/(?P<city>[A-ZÇĞİÖŞÜ]+))?$",
        token.strip(),
    )
    if not m:
        return None
    going_map = {"NOR": "Normal", "YUM": "Yumuşak", "AĞR": "Ağır", "AGIR": "Ağır", "BIR": "Biraz"}
    city_map = {"ADA": "Adana", "IST": "İstanbul", "ANK": "Ankara", "IZM": "İzmir", "BUR": "Bursa"}
    time_sec = pace_to_seconds(m.group("t"))
    if time_sec is None:
        return None
    going = going_map.get((m.group("going") or "").upper(), m.group("going") or "Normal")
    city = city_map.get((m.group("city") or "").upper(), m.group("city") or "")
    return time_sec, going, city


def parse_bulletin_text(raw_text: str) -> Dict[str, Any]:
    """
    Bülten metnini kaba bir şekilde modele girecek sözlük yapısına çevirir.
    Bu parser gevşek/heuristic çalışır; eksik alanları boş bırakır.
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    normalized = " ".join(lines)

    race_ctx: Dict[str, Any] = {
        "city": "",
        "surface": "Kum",
        "distance": 0,
        "going": "Normal",
        "breed": "İngiliz",
        "age_group": "3 Yaşlı",
        "race_class": "",
        "is_maiden": False,
    }

    meta = re.search(r"PROGRAM\s+(.+?)\s+([A-ZÇĞİÖŞÜ]+)\s+(\d+)\.\s*KOŞU", normalized, flags=re.IGNORECASE)
    if meta:
        city = meta.group(2).title().replace("İ", "İ")
        race_ctx["city"] = city

    detail = re.search(r"(ŞRT-\d+)\s+(\d+)\s*M\s+(.+?)\s*\(", normalized, flags=re.IGNORECASE)
    if detail:
        race_ctx["race_class"] = detail.group(1).upper()
        race_ctx["distance"] = int(detail.group(2))
        breed_block = detail.group(3).upper()
        race_ctx["breed"] = "İngiliz" if "İNG" in breed_block or "ING" in breed_block else "Arap"
        race_ctx["age_group"] = "3 Yaşlı" if "3 YAŞLI" in breed_block else ""

    runner_lines = [ln for ln in lines if re.match(r"^\d+\s+[A-ZÇĞİÖŞÜ]", ln)]
    runners: List[Dict[str, Any]] = []
    for ln in runner_lines:
        num_match = re.match(r"^(?P<no>\d+)\s+", ln)
        if not num_match:
            continue
        no = int(num_match.group("no"))

        agf_match = re.search(r"%\s*(?P<agf>\d+(?:\.\d+)?)\(\d+\)", ln)
        gny_match = re.search(r"(?P<gny>\d+(?:\.\d+)?)\s*$", ln)
        hp_match = re.search(r"\s(?P<hp>\d{1,2})\s+[A-ZÇĞİÖŞÜ]+\.", ln)
        kg_match = re.search(r"\s(?P<kg>\d{2})\s+[A-ZÇĞİÖŞÜ]\.", ln)
        best_match = re.search(r"(\d+/\d+\.\d+\.\d+(?:/[A-ZÇĞİÖŞÜ]+){0,2})", ln)

        name_block = re.sub(r"^\d+\s+", "", ln)
        name_block = re.split(r"\s+\d{1,2}\s+[A-ZÇĞİÖŞÜ]+\.", name_block, maxsplit=1)[0].strip()

        race_records: List[Dict[str, Any]] = []
        if best_match:
            parsed = _parse_best_degree_token(best_match.group(1))
            if parsed:
                t_sec, going, city = parsed
                race_records.append(
                    {
                        "date": "",
                        "city": city or race_ctx["city"],
                        "surface": race_ctx["surface"],
                        "distance": race_ctx["distance"],
                        "going": going,
                        "race_class": race_ctx["race_class"],
                        "position": None,
                        "time_sec": t_sec,
                        "weight": kg_match and float(kg_match.group("kg")) or None,
                        "jockey": None,
                        "hp": hp_match and float(hp_match.group("hp")) or None,
                        "start_no": None,
                    }
                )

        runners.append(
            {
                "no": no,
                "name": name_block,
                "age_group": race_ctx["age_group"],
                "breed": race_ctx["breed"],
                "sex": None,
                "race_weight": kg_match and float(kg_match.group("kg")) or 0.0,
                "jockey": "",
                "trainer": None,
                "start_no": None,
                "hp": hp_match and float(hp_match.group("hp")) or None,
                "gp": None,
                "agf": agf_match and float(agf_match.group("agf")) or None,
                "equipment": None,
                "race_records": race_records,
                "workouts": [],
                "market_odds": gny_match and float(gny_match.group("gny")) or None,
            }
        )

    return {"race_context": race_ctx, "runners": runners}


def split_large_bulletin_text(raw_text: str, max_chars: int = 4000) -> List[str]:
    """
    Çok uzun bülten/OCR metinlerini satır bazında parçalar.
    PDF'den kopyalanan verilerde tek seferde parse zorlaşırsa chunk-parsing için kullanılır.
    """
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    chunks: List[str] = []
    buf: List[str] = []
    current_len = 0
    for ln in lines:
        ln_len = len(ln) + 1
        if current_len + ln_len > max_chars and buf:
            chunks.append("\n".join(buf))
            buf = [ln]
            current_len = ln_len
        else:
            buf.append(ln)
            current_len += ln_len
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def parse_bulletin_chunks(chunks: List[str]) -> Dict[str, Any]:
    """
    Uzun bültenleri parça parça parse edip tek yarış yapısında birleştirir.
    - race_context: ilk dolu gelen context tercih edilir
    - runners: at no bazında birleştirilir
    """
    merged_ctx: Dict[str, Any] = {}
    merged_runners: Dict[int, Dict[str, Any]] = {}

    for chunk in chunks:
        parsed = parse_bulletin_text(chunk)
        ctx = parsed.get("race_context", {})
        runners = parsed.get("runners", [])

        if not merged_ctx:
            merged_ctx = dict(ctx)
        else:
            for k, v in ctx.items():
                if (merged_ctx.get(k) in ("", 0, None)) and v not in ("", 0, None):
                    merged_ctx[k] = v

        for r in runners:
            no = int(r["no"])
            if no not in merged_runners:
                merged_runners[no] = r
            else:
                base = merged_runners[no]
                for key, val in r.items():
                    if key in ("race_records", "workouts"):
                        continue
                    if (base.get(key) in ("", 0, None)) and val not in ("", 0, None):
                        base[key] = val
                if r.get("race_records"):
                    base_rr = base.setdefault("race_records", [])
                    seen = {(x.get("time_sec"), x.get("distance"), x.get("city")) for x in base_rr}
                    for rr in r["race_records"]:
                        sig = (rr.get("time_sec"), rr.get("distance"), rr.get("city"))
                        if sig not in seen:
                            base_rr.append(rr)
                            seen.add(sig)

    merged_list = [merged_runners[k] for k in sorted(merged_runners)]
    return {"race_context": merged_ctx, "runners": merged_list}


if __name__ == "__main__":
    print("Race model calibration module hazır. Bu dosya veri parser ile beslenip yarış bazlı kullanılmalıdır.")
