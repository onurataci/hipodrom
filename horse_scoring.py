from math import sqrt
from datetime import datetime


DATE_FMT = "%d/%m/%Y"


def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def std_pop(vals):
    if not vals:
        return 0.0
    m = mean(vals)
    return sqrt(sum((x - m) ** 2 for x in vals) / len(vals))


def zscores(vals):
    s = std_pop(vals)
    if s == 0:
        return [0.0] * len(vals)
    m = mean(vals)
    return [(x - m) / s for x in vals]


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def _parse_date(s):
    return datetime.strptime(s, DATE_FMT).date()


def _best_time(gallops, distance):
    vals = [g["time"] for g in gallops if g.get("distance") == distance and g.get("time") is not None]
    return min(vals) if vals else None


def _latest_gallop(gallops):
    return max(gallops, key=lambda g: _parse_date(g["date"])) if gallops else None


def _recent_count(gallops, race_date, days=21):
    rd = _parse_date(race_date)
    return sum(1 for g in gallops if (rd - _parse_date(g["date"])).days <= days)


def enrich_from_gallops(row, race_date):
    gallops = row.get("gallops", [])
    latest = _latest_gallop(gallops)
    row["best_400"] = _best_time(gallops, 400)
    row["best_600"] = _best_time(gallops, 600)
    row["best_800"] = _best_time(gallops, 800)
    row["recent_work_count"] = _recent_count(gallops, race_date, days=21)

    if latest:
        row["last_gallop_city"] = latest.get("city")
        row["last_gallop_jokey"] = latest.get("jokey")
        row["last_gallop_kg"] = latest.get("kg")
        row["last_gallop_date"] = latest.get("date")
    else:
        row["last_gallop_city"] = row.get("hipodrom")
        row["last_gallop_jokey"] = row.get("jokey_kosu")
        row["last_gallop_kg"] = row.get("kilo_kosu")
        row["last_gallop_date"] = race_date


def calculate_scores(rows, race_date="04/05/2026"):
    for r in rows:
        enrich_from_gallops(r, race_date)

    # distance-aware speed input (400 and 600 primary, 800 secondary)
    s400 = [r["best_400"] if r["best_400"] is not None else 999.0 for r in rows]
    s600 = [r["best_600"] if r["best_600"] is not None else 999.0 for r in rows]
    s800 = [r["best_800"] if r["best_800"] is not None else 999.0 for r in rows]
    z400, z600, z800 = zscores(s400), zscores(s600), zscores(s800)

    sorted_gates = sorted({r["start_no"] for r in rows})
    gate_index = {g: i for i, g in enumerate(sorted_gates)}
    max_i = max(len(sorted_gates) - 1, 1)
    race_dt = _parse_date(race_date)

    for i, r in enumerate(rows):
        r["jokey_match"] = int(r["jokey_kosu"] == r["last_gallop_jokey"])
        r["city_match"] = int(r["hipodrom"] == r["last_gallop_city"])
        r["kg_diff_lastwork"] = r["kilo_kosu"] - r["last_gallop_kg"]

        speed_component = (-z400[i] * 0.5) + (-z600[i] * 0.35) + (-z800[i] * 0.15)
        score_speed = clip(20 + 7 * speed_component, 0, 35)

        # recency/workload contribution
        days_since = (race_dt - _parse_date(r["last_gallop_date"])).days
        score_recency = clip(8 - days_since * 0.4, 0, 8) + clip(r["recent_work_count"] * 0.8, 0, 5)

        hp = r.get("hp")
        r["hp_per_kg"] = (hp / r["kilo_kosu"]) if hp is not None and hp > 0 else None

        score_kg_dyn = clip(15 - abs(r["kg_diff_lastwork"] - 0.5) * 4, 0, 15)
        score_jokey = 10 if r["jokey_match"] else 0
        score_city = 10 if r["city_match"] else 0
        score_start = clip(10 - gate_index[r["start_no"]] * (10 / max_i), 0, 10)
        score_agf = clip((r.get("agf", 0) / 40) * 8, 0, 8)

        if r["hp_per_kg"] is None:
            score_speed = clip(score_speed + 8, 0, 43)
            score_start = clip(score_start + 3, 0, 13)
            score_kg_dyn = clip(score_kg_dyn + 4, 0, 19)
            score_hpkg = 0
        else:
            score_hpkg = 10

        r["final_score"] = round(
            score_speed + score_hpkg + score_kg_dyn + score_jokey + score_city + score_start + score_recency + score_agf,
            2,
        )

    rows.sort(key=lambda x: x["final_score"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank_pred"] = i
        r["label"] = "Favori" if i <= 2 else ("Rakip" if i <= 4 else "Sürpriz")
    return rows


def sample_bursa_r1():
    return [
        {"no":1,"at_adi":"AKSA ASLANI","kilo_kosu":57,"jokey_kosu":"Y.CENGIZ","start_no":9,"hp":None,"hipodrom":"Bursa","agf":21.03,
         "gallops":[{"distance":600,"time":55.8,"date":"02/05/2026","city":"Bursa","jokey":"D.SENBAHAR","kg":55},{"distance":400,"time":26.3,"date":"02/05/2026","city":"Bursa","jokey":"D.SENBAHAR","kg":55},{"distance":600,"time":56.1,"date":"28/03/2026","city":"Sanliurfa","jokey":"Y.CENGIZ","kg":57}]},
        {"no":2,"at_adi":"ASALET SAHIBI","kilo_kosu":57,"jokey_kosu":"O.GOKCE","start_no":6,"hp":None,"hipodrom":"Bursa","agf":7.05,
         "gallops":[{"distance":600,"time":56.5,"date":"02/05/2026","city":"Bursa","jokey":"O.GOKCE","kg":54},{"distance":400,"time":27.6,"date":"02/05/2026","city":"Bursa","jokey":"O.GOKCE","kg":54}]},
        {"no":3,"at_adi":"BARLABEY","kilo_kosu":57,"jokey_kosu":"H.TURAN","start_no":4,"hp":None,"hipodrom":"Bursa","agf":2.68,
         "gallops":[{"distance":600,"time":58.0,"date":"01/05/2026","city":"Bursa","jokey":"H.TURAN","kg":58},{"distance":400,"time":28.4,"date":"01/05/2026","city":"Bursa","jokey":"H.TURAN","kg":58},{"distance":600,"time":42.0,"date":"22/03/2026","city":"Bursa","jokey":"M.TOKCALAR","kg":54}]},
        {"no":4,"at_adi":"BARLIN AGA","kilo_kosu":57,"jokey_kosu":"H.KARATAS","start_no":1,"hp":None,"hipodrom":"Bursa","agf":38.04,
         "gallops":[{"distance":600,"time":40.4,"date":"01/05/2026","city":"Bursa","jokey":"S.BASKAN","kg":59},{"distance":400,"time":26.4,"date":"01/05/2026","city":"Bursa","jokey":"S.BASKAN","kg":59}]},
        {"no":5,"at_adi":"KOLAYSA YAKALA","kilo_kosu":57,"jokey_kosu":"MAH.TURAN","start_no":3,"hp":None,"hipodrom":"Bursa","agf":5.89,
         "gallops":[{"distance":600,"time":57.0,"date":"01/05/2026","city":"Bursa","jokey":"A.SENBAHAR","kg":58},{"distance":400,"time":28.2,"date":"01/05/2026","city":"Bursa","jokey":"A.SENBAHAR","kg":58},{"distance":600,"time":41.5,"date":"26/04/2026","city":"Bursa","jokey":"MAH.TURAN","kg":55}]},
        {"no":6,"at_adi":"KRAL KADIR","kilo_kosu":57,"jokey_kosu":"B.M.MIRIK","start_no":7,"hp":None,"hipodrom":"Bursa","agf":6.22,
         "gallops":[{"distance":600,"time":56.0,"date":"01/05/2026","city":"Bursa","jokey":"O.ALTIN","kg":55},{"distance":400,"time":27.8,"date":"01/05/2026","city":"Bursa","jokey":"O.ALTIN","kg":55},{"distance":400,"time":26.8,"date":"24/04/2026","city":"Bursa","jokey":"E.OZKAN","kg":57}]},
        {"no":7,"at_adi":"SAVASCI BEDIR","kilo_kosu":57,"jokey_kosu":"S.CETIN","start_no":10,"hp":None,"hipodrom":"Bursa","agf":6.27,
         "gallops":[{"distance":600,"time":40.8,"date":"02/05/2026","city":"Bursa","jokey":"S.CETIN","kg":57},{"distance":400,"time":27.3,"date":"02/05/2026","city":"Bursa","jokey":"S.CETIN","kg":57},{"distance":600,"time":41.7,"date":"22/02/2026","city":"Antalya","jokey":"N.BAYDAN","kg":63}]},
        {"no":8,"at_adi":"ALAKARTAL","kilo_kosu":55,"jokey_kosu":"S.TIRPAN","start_no":5,"hp":None,"hipodrom":"Bursa","agf":3.34,
         "gallops":[{"distance":600,"time":56.0,"date":"01/05/2026","city":"Bursa","jokey":"APRANTI","kg":55},{"distance":400,"time":28.0,"date":"01/05/2026","city":"Bursa","jokey":"APRANTI","kg":55}]},
        {"no":9,"at_adi":"DIKKALDIRIM","kilo_kosu":55,"jokey_kosu":"C.TASCI","start_no":2,"hp":None,"hipodrom":"Bursa","agf":1.14,
         "gallops":[{"distance":600,"time":57.5,"date":"01/05/2026","city":"Bursa","jokey":"O.BALKAN","kg":54},{"distance":400,"time":28.5,"date":"01/05/2026","city":"Bursa","jokey":"O.BALKAN","kg":54}]},
        {"no":10,"at_adi":"GUL MEVSIMI","kilo_kosu":55,"jokey_kosu":"E.AKPINAR","start_no":12,"hp":None,"hipodrom":"Bursa","agf":1.23,
         "gallops":[{"distance":600,"time":44.8,"date":"30/04/2026","city":"Bursa","jokey":"F.HIM","kg":57},{"distance":400,"time":28.6,"date":"30/04/2026","city":"Bursa","jokey":"F.HIM","kg":57}]},
        {"no":11,"at_adi":"LADY BRIDGERTON","kilo_kosu":55,"jokey_kosu":"T.ALICI","start_no":11,"hp":None,"hipodrom":"Bursa","agf":3.84,
         "gallops":[{"distance":600,"time":43.0,"date":"01/05/2026","city":"Bursa","jokey":"O.BALKAN","kg":54},{"distance":400,"time":28.7,"date":"01/05/2026","city":"Bursa","jokey":"O.BALKAN","kg":54},{"distance":600,"time":42.3,"date":"08/03/2026","city":"Bursa","jokey":"T.ALICI","kg":59},{"distance":400,"time":28.0,"date":"08/03/2026","city":"Bursa","jokey":"T.ALICI","kg":59}]},
        {"no":12,"at_adi":"TURQUOISE","kilo_kosu":55,"jokey_kosu":"T.YILDIZ","start_no":8,"hp":None,"hipodrom":"Bursa","agf":3.27,
         "gallops":[{"distance":600,"time":58.6,"date":"02/05/2026","city":"Bursa","jokey":"A.SENBAHAR","kg":58},{"distance":400,"time":29.3,"date":"02/05/2026","city":"Bursa","jokey":"A.SENBAHAR","kg":58},{"distance":400,"time":27.4,"date":"30/04/2026","city":"Bursa","jokey":"A.SENBAHAR","kg":58}]},
    ]


def render_chat_table(rows):
    lines = [
        "| Sıra | No | At | Skor | Etiket | AGF% | En iyi 400 | En iyi 600 | Son Galop KG | KG Fark |",
        "|---:|---:|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['rank_pred']} | {r['no']} | {r['at_adi']} | {r['final_score']:.2f} | {r['label']} | {r.get('agf',0):.2f} | {r['best_400']:.1f} | {r['best_600']:.1f} | {r['last_gallop_kg']:.0f} | {r['kg_diff_lastwork']:.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    scored = calculate_scores(sample_bursa_r1(), race_date="04/05/2026")
    print(render_chat_table(scored))
