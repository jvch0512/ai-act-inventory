"""AI Act inventory checks. Standard library only."""
import csv
import io

RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
CLASSES = ("prohibited", "high", "limited", "minimal")
ANNEX3 = ("biometrics", "critical_infrastructure", "education", "employment",
          "essential_services", "law_enforcement", "migration", "justice")
PROHIBITED = ("social scoring", "social score", "scraping facial", "facial image scraping",
              "untargeted scraping", "subliminal", "real-time remote biometric", "predictive policing of individuals",
              "exploit vulnerabilities")
# Added to Article 5 by the Digital Omnibus on AI, Regulation (EU) 2026/1744 (in force 27 July 2026, applying from 2 December 2026).
PROHIBITED_2026 = ("nudif", "undress", "non-consensual intimate", "nonconsensual intimate", "child sexual abuse", "csam")
# Emotion recognition is banned at work and in education, and is an Annex III high-risk use elsewhere.
WORK_EDU = ("workplace", "at work", "employee", "staff", "school", "student", "classroom", "education", "pupil")
LIMITED = ("chatbot", "virtual assistant", "deepfake", "synthetic media", "generated content", "generative", "text generation",
           "image generation", "voice cloning")


def finding(sev, rule, file, line, msg):
    return {"sev": sev, "rule": rule, "file": file, "line": line, "msg": msg,
            "where": f"{file}:{line}" if line else file}


def yes(v):
    return v.strip().lower() in ("yes", "true", "1", "y")


def audit(text, label):
    out = []
    try:
        rows = list(csv.reader(io.StringIO(text.replace("\x00", ""), newline="")))
    except csv.Error:
        return [finding("info", "AIA000", label, 0, "not valid CSV, ignored")]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return [finding("info", "AIA000", label, 0, "empty file, nothing to check")]
    head = [h.strip().lower() for h in rows[0]]
    if "name" not in head or "risk_class" not in head:
        return [finding("info", "AIA000", label, 0, "no header with name and risk_class columns")]
    idx = {h: i for i, h in enumerate(head)}
    # recompute physical line numbers (quoted newlines make rows span lines)
    lines = _row_lines(text)
    for n, r in enumerate(rows[1:], start=1):
        ln = lines[n] if n < len(lines) else n + 1

        def col(k):
            i = idx.get(k)
            return r[i].strip() if i is not None and i < len(r) else ""
        name = col("name") or "(unnamed)"
        purpose = col("purpose").lower()
        domain = col("domain").lower()
        rc = col("risk_class").lower()
        emotion = "emotion recognition" in purpose or "emotion detection" in purpose
        emotion_banned = emotion and (domain in ("employment", "education") or any(k in purpose for k in WORK_EDU))
        if any(k in purpose for k in PROHIBITED) or emotion_banned:
            out.append(finding("critical", "AIA001", label, ln, f"{name}: the purpose looks like a prohibited practice under Article 5, stop and review with legal"))
        elif any(k in purpose for k in PROHIBITED_2026):
            out.append(finding("critical", "AIA001", label, ln, f"{name}: the purpose looks like the Article 5 ban on non-consensual intimate imagery and child sexual abuse material added by Regulation (EU) 2026/1744 (applies from 2 December 2026), stop and review with legal"))
        elif emotion and rc not in ("high", "prohibited"):
            out.append(finding("high", "AIA002", label, ln, f"{name}: emotion recognition is an Annex III high-risk use (point 1(c)) outside work and education, but risk_class is '{rc or 'empty'}'"))
        high_domain = domain in ANNEX3
        if rc not in CLASSES:
            out.append(finding("low", "AIA009", label, ln, f"{name}: risk_class is empty or not one of {', '.join(CLASSES)}"))
        if high_domain and rc != "high" and rc != "prohibited":
            out.append(finding("high", "AIA002", label, ln, f"{name}: domain '{domain}' is an Annex III high-risk area but risk_class is '{rc or 'empty'}'"))
        is_high = rc == "high" or ((high_domain or emotion) and rc != "prohibited")
        if is_high:
            if not yes(col("human_oversight")):
                out.append(finding("high", "AIA003", label, ln, f"{name}: high-risk system without human oversight"))
            if not yes(col("logging")):
                out.append(finding("medium", "AIA004", label, ln, f"{name}: high-risk system without automatic logging"))
            if not yes(col("data_governance")):
                out.append(finding("medium", "AIA005", label, ln, f"{name}: high-risk system without data governance"))
            if not col("conformity_assessment_date"):
                out.append(finding("medium", "AIA006", label, ln, f"{name}: high-risk system with no conformity assessment date"))
        if (rc == "limited" or any(k in purpose for k in LIMITED)) and not yes(col("transparency_notice")):
            out.append(finding("medium", "AIA007", label, ln, f"{name}: interacts with people or generates content without a transparency notice"))
        if not col("owner"):
            out.append(finding("low", "AIA008", label, ln, f"{name}: no owner named"))
    return out


def _row_lines(text):
    """Physical start line of each non-blank CSV record (1-based)."""
    res, line, i, n, q = [], 1, 0, len(text), False
    start, has = 1, False
    while i < n:
        c = text[i]
        if c == '"':
            if q and i + 1 < n and text[i + 1] == '"':
                i += 1
            else:
                q = not q
            has = True
        elif c == "\n":
            if q:
                has = True
            else:
                if has:
                    res.append(start)
                has = False
                start = line + 1
            line += 1
        elif c == "\r":
            pass
        elif not c.isspace() or q:
            has = True
        i += 1
    if has:
        res.append(start)
    return res


def sort_findings(fs):
    return sorted(fs, key=lambda f: (RANK[f["sev"]], f["file"], f["line"], f["rule"]))
