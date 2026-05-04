from math import sqrt


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


def calculate_scores(rows):
    # rows: list[dict]
    g400 = [r["last_gallop_400"] for r in rows]
    g600 = [r["last_gallop_600"] for r in rows]
    z400 = zscores(g400)
    z600 = zscores(g600)

    # start gate score (low gate better)
    sorted_gates = sorted({r["start_no"] for r in rows})
    gate_index = {g: i for i, g in enumerate(sorted_gates)}
    max_i = max(len(sorted_gates) - 1, 1)

    for i, r in enumerate(rows):
        r["jokey_match"] = int(r["jokey_kosu"] == r["last_gallop_jokey"])
        r["city_match"] = int(r["hipodrom"] == r["last_gallop_city"])
        r["kg_diff_lastwork"] = r["kilo_kosu"] - r["last_gallop_kg"]

        speed_component = (-z400[i] * 0.6) + (-z600[i] * 0.4)
        score_speed = clip(22 + 6 * speed_component, 0, 35)

        # HP/KG (optional)
        hp = r.get("hp")
        if hp is not None and hp > 0:
            r["hp_per_kg"] = hp / r["kilo_kosu"]
        else:
            r["hp_per_kg"] = None

        score_kg_dyn = clip(15 - abs(r["kg_diff_lastwork"] - 0.5) * 4, 0, 15)
        score_jokey = 10 if r["jokey_match"] else 0
        score_city = 10 if r["city_match"] else 0
        score_start = clip(10 - gate_index[r["start_no"]] * (10 / max_i), 0, 10)

        # Maiden fallback if HP missing
        if r["hp_per_kg"] is None:
            score_speed = clip(score_speed + 10, 0, 45)
            score_start = clip(score_start + 5, 0, 15)
            score_kg_dyn = clip(score_kg_dyn + 5, 0, 20)
            score_hpkg = 0
        else:
            score_hpkg = 10  # placeholder; in mixed fields can zscore hp_per_kg

        r["score_speed"] = round(score_speed, 2)
        r["score_hpkg"] = round(score_hpkg, 2)
        r["score_kg_dyn"] = round(score_kg_dyn, 2)
        r["score_jokey"] = score_jokey
        r["score_city"] = score_city
        r["score_start"] = round(score_start, 2)

        r["final_score"] = round(
            r["score_speed"]
            + r["score_hpkg"]
            + r["score_kg_dyn"]
            + r["score_jokey"]
            + r["score_city"]
            + r["score_start"],
            2,
        )

    rows.sort(key=lambda x: x["final_score"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank_pred"] = i
        r["label"] = "Favori" if i <= 2 else ("Rakip" if i <= 4 else "Sürpriz")

    return rows


def sample_bursa_r1():
    return [
        {"no": 1, "at_adi": "AKSA ASLANI", "kilo_kosu": 57, "jokey_kosu": "Y.CENGIZ", "start_no": 9, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "D.SENBAHAR", "last_gallop_kg": 55, "last_gallop_400": 26.3, "last_gallop_600": 55.8, "hipodrom": "Bursa"},
        {"no": 2, "at_adi": "ASALET SAHIBI", "kilo_kosu": 57, "jokey_kosu": "O.GOKCE", "start_no": 6, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "O.GOKCE", "last_gallop_kg": 54, "last_gallop_400": 27.6, "last_gallop_600": 56.5, "hipodrom": "Bursa"},
        {"no": 3, "at_adi": "BARLABEY", "kilo_kosu": 57, "jokey_kosu": "H.TURAN", "start_no": 4, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "H.TURAN", "last_gallop_kg": 58, "last_gallop_400": 28.4, "last_gallop_600": 58.0, "hipodrom": "Bursa"},
        {"no": 4, "at_adi": "BARLIN AGA", "kilo_kosu": 57, "jokey_kosu": "H.KARATAS", "start_no": 1, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "S.BASKAN", "last_gallop_kg": 59, "last_gallop_400": 26.4, "last_gallop_600": 40.4, "hipodrom": "Bursa"},
        {"no": 5, "at_adi": "KOLAYSA YAKALA", "kilo_kosu": 57, "jokey_kosu": "MAH.TURAN", "start_no": 3, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "A.SENBAHAR", "last_gallop_kg": 58, "last_gallop_400": 28.2, "last_gallop_600": 57.0, "hipodrom": "Bursa"},
        {"no": 6, "at_adi": "KRAL KADIR", "kilo_kosu": 57, "jokey_kosu": "B.M.MIRIK", "start_no": 7, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "O.ALTIN", "last_gallop_kg": 55, "last_gallop_400": 27.8, "last_gallop_600": 56.0, "hipodrom": "Bursa"},
        {"no": 7, "at_adi": "SAVASCI BEDIR", "kilo_kosu": 57, "jokey_kosu": "S.CETIN", "start_no": 10, "hp": None, "last_gallop_city": "Bursa", "last_gallop_jokey": "S.CETIN", "last_gallop_kg": 57, "last_gallop_400": 27.3, "last_gallop_600": 40.8, "hipodrom": "Bursa"},
    ]


def print_table(rows):
    headers = ["Rnk", "No", "At", "Skor", "Etiket", "400", "600", "KgFark", "JokeyU", "StartS"]
    print(" | ".join(headers))
    print("-" * 92)
    for r in rows:
        print(f"{r['rank_pred']:>3} | {r['no']:>2} | {r['at_adi']:<15} | {r['final_score']:>5.2f} | {r['label']:<7} | "
              f"{r['last_gallop_400']:>4.1f} | {r['last_gallop_600']:>4.1f} | {r['kg_diff_lastwork']:>6.1f} | {r['jokey_match']:>6} | {r['score_start']:>6.2f}")


def print_predictions(rows):
    favori = [r for r in rows if r["label"] == "Favori"]
    rakip = [r for r in rows if r["label"] == "Rakip"]
    surpriz = [r for r in rows if r["label"] == "Sürpriz"]

    print("\nTAHMINLER")
    print("=" * 30)
    print("Favoriler:", ", ".join(f"{r['no']}-{r['at_adi']}" for r in favori) or "Yok")
    print("Rakipler :", ", ".join(f"{r['no']}-{r['at_adi']}" for r in rakip) or "Yok")
    print("Surpriz  :", ", ".join(f"{r['no']}-{r['at_adi']}" for r in surpriz) or "Yok")

    if len(rows) >= 2:
        a, b = rows[0], rows[1]
        print("\nOyun onerisi:")
        print(f"- Ganyan: {a['no']} {a['at_adi']}")
        print(f"- Ikili : {a['no']}-{b['no']}")
        print(f"- Sirali Ikili: {a['no']}/{b['no']} (sigorta: {b['no']}/{a['no']})")


if __name__ == "__main__":
    data = sample_bursa_r1()
    scored = calculate_scores(data)
    print_table(scored)
    print_predictions(scored)
