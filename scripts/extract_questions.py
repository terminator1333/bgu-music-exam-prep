#!/usr/bin/env python3
"""Extract Hebrew multiple-choice questions from the course .docx quizzes and
combine them with a hand-curated list of questions derived from the slides.

Output: app/questions.json — a flat list of {id, lesson, lesson_title,
source, question, options[4], correct}.

Run: python3 scripts/extract_questions.py
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "app" / "questions.json"

LESSON_TITLES = {
    1: "היכרות עם התזמורת",
    2: "סוגות וצורות",
    3: "כלי המיתר",
    4: "כלי נשיפה והקשה",
    5: "הפסנתר כסולן בתזמורת",
    6: "הקול האנושי והאופרה",
}

# Hand-authored 1-2 sentence Hebrew explanations, keyed by question ID.
# Missing entries are fine — the app skips them silently.
EXPLANATIONS: dict[str, str] = {
    "L1Q01": "מוצרט (1756–1791) פעל בשלהי המאה ה-18, במרכז התקופה הקלאסית. ויוואלדי שייך לבארוק, ושופן וצ׳ייקובסקי לתקופה הרומנטית.",
    "L1Q02": "הרומנטיקה שמה במרכז את הרגש של היוצר ואת הביטוי האישי, במקום הסימטריה וההקפדה הפורמלית של התקופה הקלאסית שקדמה לה.",
    "L1Q03": "הרנסאנס (המאות 15–16) הוא התקופה שבה פרחה מחדש המוזיקה החילונית לצד הרפרטואר הדתי של הכנסייה.",
    "L1Q04": "ההבדל הבסיסי הוא כמותי: תזמורת קאמרית קטנה בהרבה (עשרות נגנים או פחות) ואילו סימפונית מונה 60–100 נגנים.",
    "L1Q05": "המנצח גם קובע טמפו וגם מפרש את כוונת המלחין, ולכן שתי התשובות נכונות. ״לכוון״ את הכלים אינו תפקידו — הנגנים מכוונים בעצמם לפני הקונצרט.",
    "L1Q06": "המזמורים הגרגוריאניים נוצרו במערכת הדתית של ימי הביניים ונקראו על שם האפיפיור גרגוריוס הראשון.",
    "L1Q07": "תקופת הבארוק נפתחה סביב שנת 1600 בפירנצה עם הולדת האופרה, סוגה שמשלבת שירה סולו, תזמורת ותיאטרון.",
    "L1Q08": "מהבארוק ועד לרומנטיקה התזמורת גדלה דרמטית בגודל ובמגוון הכלים, כדי לשרת אידאלים רגשיים וצבעוניים חדשים.",
    "L1Q09": "סדר הישיבה נועד להבטיח שכל קבוצת כלים תישמע בעוצמה ובבהירות הנכונות, בהתחשב בעוצמת ההקרנה של כל כלי.",
    "L1Q10": "לאורך התקופות המוזיקה הפכה מורכבת יותר הרמונית וצורנית, ובמקביל הכללים הפורמליים התרופפו ונתנו חופש רב יותר ליוצר.",
    "L2Q01": "סוגה (ז׳אנר) מתייחסת לסוג היצירה — אופרה, סימפוניה, קונצ׳רטו — ואילו צורה מתייחסת למבנה הפנימי של היצירה או של פרקיה, למשל סונטה או רונדו.",
    "L2Q02": "סימפוניה היא יצירה גדולה לתזמורת, בדרך כלל בת ארבעה פרקים עם אופי שונה זה מזה.",
    "L2Q03": "הסטנדרט הקלאסי הוא סימפוניה בת ארבעה פרקים וקונצ׳רטו בן שלושה (מהיר–איטי–מהיר).",
    "L2Q04": "בקונצ׳רטו היחס מורכב יותר: יש פתיחה תזמורתית, דיאלוג בין הסולן לתזמורת, ולעתים התזמורת מוליכה את הנושא בזמן שהסולן מנגן בליווי.",
    "L2Q05": "אוברטורה היא יצירה פותחת — במקור לפני אופרה או בלט — ובהמשך גם יצירה שעומדת בפני עצמה בקונצרט.",
    "L2Q06": "אוברטורה ואופרה הן סוגות (סוגי יצירה), ורונדו הוא צורה. רק בתשובה זו מערבבות סוגות וצורות כפי שהשאלה דורשת.",
    "L2Q07": "מינואט-טריו וסקרצו-טריו בנויים A–B–A, וגם צורת הסונטה היא מעין ABA (תצוגה–פיתוח–מחזר). נושא ווריאציות הוא מבנה לינארי, לא סימטרי.",
    "L2Q08": "זה שלד צורת הסונטה: הנושאים מוצגים, אחר כך מפותחים, ולבסוף חוזרים במחזר.",
    "L2Q09": "המבוא האיטי, כאשר קיים, בא לפני התצוגה ואינו חלק ממנה. הנושאים ונושא הסיום (קודטה) כן מרכיבים את התצוגה.",
    "L2Q10": "בסימפוניה הקלאסית הפרק השלישי הוא בדרך כלל מינואט (מאוחר יותר סקרצו) עם טריו, באופי ריקודי.",
    "L3Q01": "ARCO פירושו נגינה בקשת ו-pizzicato פירושו פריטה באצבעות, ושניהם טכניקות להפקת הצליל בכלי מיתר — ולכן גם תשובה א׳ וגם ג׳ נכונות.",
    "L3Q02": "הגשר נושא את המיתרים מעל גוף הכלי ומעביר את הרטט למכסה הקדמי ומשם לתיבת התהודה כולה.",
    "L3Q03": "כיוון משיכת הקשת (למעלה/למטה) משפיע מאוד על המבטא ועל תחילת הצליל וסופו, ולכן טענה זו לא נכונה. שאר ההיגדים בשאלה נכונים.",
    "L3Q04": "״הנשמה״ היא מוט עץ קטן בתוך הכלי שמחבר בין המכסה העליון לתחתון ומעביר ביניהם את הרטט. בלעדיו הכלי כמעט ואינו מצלצל.",
    "L3Q05": "קיצור המיתר הפעיל מעלה את תדר הרטט שלו ולכן מעלה את גובה הצליל — זה העיקרון מאחורי לחיצת האצבעות על הצוואר.",
    "L3Q06": "קונטרפונקט הוא ״קולות״ מלודיים המתנהלים במקביל, כל אחד עצמאי מבחינה קצבית ומלודית, אך משתלבים יחד הרמונית.",
    "L3Q07": "בפוגה הנושא הראשי מוצג בקול אחד ואז עובר מקול לקול בתורנות. אין חובה של 3 או 4 קולות דווקא, ולא כל קונטרפונקט הוא פוגה.",
    "L3Q08": "סגנונו של באך נחשב מיושן בימיו, כאשר הסגנון הגלנט כבר תפס את מקומו, ולצד זה היו לו עשרה ילדים בוגרים ובהם כמה מוזיקאים מפורסמים (למשל ק.פ.א. באך). לכן שתי התשובות נכונות.",
    "L3Q09": "מוצרט נסע רבות באירופה כילד פלא והטמיע את הסגנונות האיטלקי, הגרמני והצרפתי ביצירתו.",
    "L3Q10": "סולם הוא רצף סדור של צלילים בגבהים עולים או יורדים, למשל שבעת הצלילים של סולם דו מז׳ור.",
    "L4Q01": "האבוב בנוי עם שתי סוֹפיוֹת קטנות הרוטטות זו כנגד זו — משפחת הסופית הכפולה. הקלרינט משתמש בסופית בודדת, והחליל והפיקולו הם Air Jet ללא סופית.",
    "L4Q02": "בחליל הצד הצליל מופק כאשר הנגן נושף על-פני חור צדדי וגורם לאוויר שבפנים לרטוט, בלי סוֹפית ובלי פייה פנימית.",
    "L4Q03": "בכלי נשיפה ממתכת (פליז) השפתיים עצמן רוטטות לתוך הפייה, ומהוות את המקור הפיזיקלי של הצליל.",
    "L4Q04": "חצוצרות וקרנות טבעיות היו חסרות שסתומים, ולכן יכלו לנגן רק את הצלילים של הסדרה ההרמונית הטבעית, המבוססת על אורך הצינור הקבוע.",
    "L4Q05": "גובה הצליל בכלי נשיפה נקבע באורך עמודת האוויר (שמשתנה דרך שסתומים או חורים) ובעוצמת הנשיפה, שקובעת על איזו הרמוניה ״מתיישבים״.",
    "L4Q06": "לחצוצרה פייה דמוית כוס ולקרן פייה חרוטית, והצינור של הקרן ארוך ועטוף כפיף. הפרמטרים האלה יוצרים גוון שונה לחלוטין.",
    "L4Q07": "כלי הקשה ללא פיץ׳ — תוף גדול, צלחות, משולש ודומיהם — מפיקים צליל רעשני בלי גובה צליל מוגדר.",
    "L4Q08": "היידן, מוצרט ובטהובן חיו ופעלו בוינה בסוף המאה ה-18 ותחילת ה-19, ושלושתם יחד נחשבים לאדריכלי הסגנון הקלאסי.",
    "L4Q09": "בטהובן הרחיב את ממדי הסימפוניה ואת האפשרויות הדרמטיות שלה, ועבד בקונטרסטים קיצוניים של עוצמה, מקצב והרמוניה.",
    "L4Q10": "הסימפוניה התשיעית הייתה פורצת דרך בשלושת ההיבטים: שילוב מקהלה וזמרים-סולנים, ציטוטים מהפרקים הקודמים בפרק האחרון, וצלילי הפתיחה הדרמטיים של הפרק הרביעי.",
    "L5Q01": "העוגב, הצ׳מבלו ופסנתר הפטישים הם כולם כלי מקלדת שקדמו לפסנתר המודרני. האקורדיון הוא כלי מאוחר יחסית ולא חלק מהשושלת שהובילה לפסנתר.",
    "L5Q02": "הצ׳מבלו פורט על המיתרים בעוצמה קבועה, בעוד שפסנתר הפטישים משתמש בפטישים קטנים שאפשר להכות בהם חזק או חלש לפי עוצמת הלחיצה — מכאן שמו ״פיאנו-פורטה״ (חלש-חזק).",
    "L5Q03": "למרות ההיסטוריה הארוכה של הפסנתר, רק במוזיקה של המאה ה-20 הוא הפך לכלי קבוע בתוך התזמורת הסימפונית. לפני כן הופיע בעיקר כסולן בקונצ׳רטי.",
    "L5Q04": "הקונצ׳רטו הקלאסי בנוי כדיאלוג אמיתי בין הסולן לתזמורת, עם חילופי נושאים והתמודדויות הדדיות — לא רק ליווי.",
    "L5Q05": "אחד השינויים של הרומנטיקה היה שבירת הכלל הקלאסי של ״פתיחה תזמורתית״ לפני כניסת הסולן. אצל שומאן, גריג ואחרים הסולן נכנס מייד בפתיחה, לעתים במחווה וירטואוזית.",
    "L5Q06": "שופן כתב כמעט אך ורק לפסנתר, והוא אחד המלחינים הגדולים היחידים שהתמקדו כך בכלי אחד.",
    "L5Q07": "ברהמס חשש מהצל הענק של בטהובן והיסס שנים רבות לפני שכתב את סימפוניה מס׳ 1 (בגיל 43). בסך הכול כתב ארבע סימפוניות.",
    "L5Q08": "המז׳ור נתפס תרבותית כצליל בהיר/שמח והמינור ככהה/עצוב. ההבדל נובע בעיקר מהטרצה — גדולה במז׳ור וקטנה במינור.",
    "L5Q09": "אקורד מז׳ור בסיסי בנוי משלושה צלילים — יסוד, טרצה גדולה וקווינטה — שכולם חלק מסולם מז׳ור אחד.",
    "L6Q01": "הקול האנושי ייחודי בכך שהוא מעביר שפה ומשמעות מילולית יחד עם הצליל והרגש, משהו שאף כלי נגינה אחר אינו יכול לעשות.",
    "L6Q02": "מקהלה סטנדרטית מחולקת ל-SATB: סופרן ואלט (נשים או ילדים) וטנור ובס (גברים).",
    "L6Q03": "סימפוניה, קונצ׳רטו וסוויטה הן כלליות ואינן מחייבות זמרים, ואילו מיסת רקוויאם היא כמעט תמיד יצירה קולית שמבוססת על הטקסט הליטורגי.",
    "L6Q04": "ליד (Lied) הוא שיר אמנותי, בדרך כלל גרמני, לקול סולו וליווי פסנתר. שוברט, שומאן וברהמס הם מהבולטים בסוגה.",
    "L6Q05": "מיסה היא הלחנה של הטקסט הליטורגי של הסעודה הקתולית. הטקסטים קבועים — קיריה, גלוריה, קרדו, סנקטוס, אגנוס דיי — ומושרים בלטינית.",
    "L6Q06": "אורטוריה היא יצירה קולית-דרמטית גדולה (בדרך כלל בנושא דתי) עם סולנים, מקהלה ותזמורת, אבל ללא תפאורה, תלבושות או משחק בימתי.",
    "L6Q07": "אריה היא ״שיר״ באופרה שמתעכב על רגש של דמות במבנה מלודי מוגדר, בעוד רצ׳יטטיב הוא דיבור-בשירה שמעביר עלילה ודיאלוגים.",
    "L6Q08": "״יבש״ (secco) משמעותו ליווי דל — רק באסו קונטינואו, לרוב צ׳מבלו וצ׳לו או בס, מתחת לקו הזמרה. ההפך הוא רצ׳יטטיב ״מלווה״ (accompagnato) עם תזמורת מלאה.",
    "L6Q09": "ג׳וזפה ורדי (1813–1901) הוא הדמות המרכזית של האופרה האיטלקית במאה ה-19, עם יצירות כמו ״לה-טראוויאטה״, ״ריגולטו״ ו-״אאידה״.",
    "L6Q10": "פוצ׳יני (1858–1924) ידוע בעלילות עזות-רגש על דמויות אנושיות מורכבות — ״לה-בוהם״, ״טוסקה״, ״מאדאם באטרפליי״.",
    "S3Q01": "pizzicato הוא טכניקה של פריטה על המיתר באצבע, במקום נגינה בקשת.",
    "S3Q02": "arco באיטלקית פירושו ״קשת״, וההוראה בפרטיטורה מורה לחזור לנגינה עם הקשת אחרי קטע pizzicato.",
    "S3Q03": "legato הוא ניגון מחובר של צלילים ברצף חלק; staccato הוא ניגון של צלילים קצרים ומופרדים זה מזה.",
    "S3Q04": "טרמולו הוא החלפת כיוון הקשת במהירות גבוהה על אותו צליל, ויוצר אפקט של רעד או מתח.",
    "S3Q05": "באך נחשב לפסגת הקונטרפונקט והפוגה, ושני המושגים מזוהים איתו יותר מאשר עם כל מלחין אחר.",
    "S3Q06": "באך (1685–1750) חי בשיא תקופת הבארוק, ונחשב לסיכום הסופי של התקופה.",
    "S4Q01": "האבוב בנוי עם שתי סופיות קטנות הרוטטות זו כנגד זו, בדיוק כמו הבסון — משפחת הסופית הכפולה.",
    "S4Q02": "בקלרינט יש סוֹף אחד (עלה יחיד) המתוח כנגד משטח הפייה — סופית בודדת.",
    "S4Q03": "חליל הצד לא משתמש בסוף כלל; הצליל נוצר מזרם אוויר (Air Jet) מעל פתח בצד הכלי.",
    "S4Q04": "החלוקה הבסיסית של כלי ההקשה היא בין כלים שמפיקים גובה צליל מדויק — כמו טימפני או קסילופון — לבין כלים שמפיקים רעש ללא גובה מוגדר.",
    "S5Q01": "הצ׳מבלו היה הכלי המקלדתי המרכזי של הבארוק, ופסנתר הפטישים — ובהמשך הפסנתר המודרני — התפתחו ממנו.",
    "S6Q01": "האופרה נולדה בפירנצה ובוונציה סביב שנת 1600, בין השאר כניסיון להחיות את הדרמה היוונית העתיקה.",
    "S6Q02": "opera seria היא אופרה רצינית, בדרך כלל בנושאים מיתולוגיים או היסטוריים; opera buffa היא אופרה קומית על דמויות יומיומיות.",
    "S6Q03": "רצ׳יטטיב הוא קטע דיבורי-מושר שבו הזמר מעביר טקסט ועלילה. שונה מאריה, שבה מתבטא רגש במבנה מלודי סגור.",
    "S6Q04": "״אאידה״ היא אופרה מפורסמת של ורדי (1871). ״לה בוהם״, ״טוסקה״ ו״מאדאם באטרפליי״ הן של פוצ׳יני.",
    "S6Q05": "״טורנדוט״ היא אופרה של פוצ׳יני (לא הושלמה על ידו). ״ריגולטו״, ״הטרובדור״ ו״אותלו״ הן של ורדי.",
}

HEBREW_LETTER_PREFIX = re.compile(r"^\s*[אבגד][.״׳'.\s]+")
NUMERIC_PREFIX = re.compile(r"^\s*\d+[.)]\s*")
# Pattern inside option lines used for the Hebrew letter prefix in some files
# (e.g. "א. ויוואלדי"). We strip it before displaying but it's NOT required.


def runs_of_paragraph(p):
    """Yield (text, bold, highlight) for each text-bearing child of a paragraph.

    <w:br/> elements inside a paragraph break the logical line, so we flush the
    current accumulator at every <w:br/>. Returns a list of virtual
    sub-paragraphs, each a list of (text, bold, highlight).
    """
    segments: list[list[tuple[str, bool, str | None]]] = [[]]
    for child in p.iter():
        if child.tag == W + "br":
            segments.append([])
        elif child.tag == W + "t":
            txt = child.text or ""
            if not txt:
                continue
            r = child.getparent() if hasattr(child, "getparent") else None
            # ElementTree has no getparent; climb via iter over <w:r>
            segments[-1].append((txt, False, None))
    # Fallback: ElementTree doesn't give parents, so redo via <w:r> walk.
    segments = [[]]
    for r in p.iter(W + "r"):
        # line break inside this run?
        for sub in list(r):
            if sub.tag == W + "br":
                segments.append([])
                continue
            if sub.tag == W + "t" and sub.text:
                rpr = r.find(W + "rPr")
                bold = rpr is not None and rpr.find(W + "b") is not None
                hl = None
                if rpr is not None:
                    h = rpr.find(W + "highlight")
                    if h is not None:
                        hl = h.get(W + "val")
                segments[-1].append((sub.text, bold, hl))
    return [s for s in segments if any(t.strip() for t, _, _ in s)]


def read_paragraphs(docx_path: Path):
    """Return list of sub-paragraphs, each a list of (text, bold, highlight)."""
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    out = []
    for p in root.iter(W + "p"):
        subs = runs_of_paragraph(p)
        for s in subs:
            out.append(s)
    return out


def sub_text(sub):
    return "".join(t for t, _, _ in sub).strip()


def sub_all_bold(sub):
    return all(b for t, b, _ in sub if t.strip())


def sub_any_yellow(sub):
    return any((h or "").lower() == "yellow" for _, _, h in sub)


TOPIC_TO_LESSON = [
    # Most specific first — Lesson 6's topic line includes "סוגות קוליות",
    # which would false-match the Lesson 2 "סוגות" keyword if checked earlier.
    ("קוליות", 6),
    ("הקול", 6),
    ("אופרה", 6),
    ("מקהלה", 6),
    ("מיתר", 3),
    ("נשיפה", 4),
    ("הקשה", 4),
    ("פסנתר", 5),
    ("סוגות", 2),
    ("צורות", 2),
    ("התזמורת", 1),
    ("היכרות", 1),
]


def detect_lesson(paragraphs) -> int | None:
    """Identify the lesson.

    Priority:
    1. Topic string (נושא: ...) matched against keyword map — most reliable.
    2. Mode of "מפגש N" / "שיעור N" mentions across the first ~15 paragraphs,
       since the true title sometimes appears after a stale header line.
    """
    topic_line = ""
    for sub in paragraphs[:15]:
        t = sub_text(sub)
        if "נושא" in t or "בנושא" in t:
            topic_line = t
            break
    if topic_line:
        for kw, lesson in TOPIC_TO_LESSON:
            if kw in topic_line:
                return lesson
    from collections import Counter
    c: Counter[int] = Counter()
    for sub in paragraphs[:15]:
        for m in re.finditer(r"(?:מפגש|שיעור)\s*(?:מס\s*)?(\d+)", sub_text(sub)):
            c[int(m.group(1))] += 1
    if c:
        return c.most_common(1)[0][0]
    return None


def clean_option(text: str) -> str:
    t = HEBREW_LETTER_PREFIX.sub("", text).strip()
    return t


def normalize_question(text: str) -> str:
    """Strip numeric prefix and normalize punctuation/whitespace for dedup."""
    t = NUMERIC_PREFIX.sub("", text).strip()
    # Remove punctuation that tends to drift between file copies; keep letters.
    t = re.sub(r"[?:.,\"׳״׳״’‘“”]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_question_line(text: str, all_bold: bool) -> bool:
    """Heuristic: a paragraph introduces a question if it ends with '?',
    starts with a number-dot prefix, or is fully bold and ends with ':'."""
    t = text.strip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    # Some questions have "?" mid-sentence followed by a parenthetical.
    if "?" in t and t.endswith(")") and len(t) > 20:
        return True
    if NUMERIC_PREFIX.match(t) and len(t) > 10:
        return True
    if t.endswith(":") and len(t) > 15:
        # Questions phrased as "X מאופיין בכך:" occur in several files and
        # are not always fully bold. Colon-ended lines this long aren't options
        # in this corpus.
        return True
    return False


def parse_questions(paragraphs):
    """Walk paragraphs and group into (question_text, [option_subs]) tuples.

    Options are the next 4 non-empty paragraphs after a question line, unless
    we hit another question line first.
    """
    items = []
    n = len(paragraphs)
    i = 0
    while i < n:
        qtext = sub_text(paragraphs[i])
        if is_question_line(qtext, sub_all_bold(paragraphs[i])):
            opts = []
            j = i + 1
            while j < n and len(opts) < 4:
                s = paragraphs[j]
                otext = sub_text(s)
                if not otext:
                    j += 1
                    continue
                if is_question_line(otext, sub_all_bold(s)):
                    break
                opts.append(s)
                j += 1
            if len(opts) == 4:
                items.append((qtext, opts))
                i = j
                continue
        i += 1
    return items


def detect_correct(opts) -> int | None:
    # 1) yellow highlight on any run in an option
    yellow_idx = [i for i, s in enumerate(opts) if sub_any_yellow(s)]
    if len(yellow_idx) == 1:
        return yellow_idx[0]
    if len(yellow_idx) > 1:
        # ambiguous; prefer the most-yellow by char count
        scores = [(sum(len(t) for t, _, h in s if (h or '').lower() == 'yellow'), i)
                  for i, s in enumerate(opts)]
        scores.sort(reverse=True)
        return scores[0][1]
    # 2) exactly one option is fully bold while others are not
    bold_flags = [sub_all_bold(s) for s in opts]
    if bold_flags.count(True) == 1 and bold_flags.count(False) == 3:
        return bold_flags.index(True)
    return None


def clean_question_display(text: str) -> str:
    """Strip leading number prefix but keep the question's punctuation."""
    t = NUMERIC_PREFIX.sub("", text).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def extract_docx_questions(path: Path, fallback_lesson: int | None):
    paragraphs = read_paragraphs(path)
    lesson = detect_lesson(paragraphs) or fallback_lesson
    raw = parse_questions(paragraphs)
    out = []
    for qtext, opts in raw:
        q_display = clean_question_display(qtext)
        q_key = normalize_question(qtext)
        option_texts = [clean_option(sub_text(s)) for s in opts]
        if not all(option_texts):
            continue
        correct = detect_correct(opts)
        out.append({
            "lesson": lesson,
            "source_file": path.name,
            "question": q_display,
            "_key": q_key,
            "options": option_texts,
            "correct": correct,
        })
    return out


# ---------------------------------------------------------------------------
# Hand-curated questions derived from slide content only.
# Each covers a fact that appears on a slide but isn't tested by the
# instructor's question bank, or reinforces a slide-level concept.
# Kept conservative (~15). source = "slides".
# ---------------------------------------------------------------------------
SLIDE_QUESTIONS = [
    {
        "lesson": 3,
        "question": "מה פירוש המונח pizzicato (פיציקטו) בכלי קשת?",
        "options": [
            "ניגון באמצעות הקשת בתנועה ארוכה",
            "פריטה על המיתר באמצעות האצבע",
            "רעידה מהירה של הקשת על המיתר",
            "השתקת המיתר בכף היד",
        ],
        "correct": 1,
    },
    {
        "lesson": 3,
        "question": "מה פירוש המונח arco בכלי קשת?",
        "options": [
            "פריטה על המיתר באמצעות האצבע",
            "ניגון באמצעות הקשת",
            "הקפצת הקשת על המיתר",
            "החלקת הקשת ללא לחץ",
        ],
        "correct": 1,
    },
    {
        "lesson": 3,
        "question": "מהו ההבדל בין legato ל-staccato?",
        "options": [
            "legato הוא ניגון מחובר וחלק, staccato הוא ניגון קצר ומופרד",
            "legato הוא ניגון קצר ומופרד, staccato הוא ניגון מחובר",
            "שניהם מתארים עוצמת נגינה",
            "שניהם מתייחסים לטמפו של היצירה",
        ],
        "correct": 0,
    },
    {
        "lesson": 3,
        "question": "מהי טכניקת tremolo בכלי קשת?",
        "options": [
            "החלפה מהירה של הקשת קדימה ואחורה על אותו צליל",
            "פריטה על מיתר אחד בלבד",
            "ניגון ללא קשת באצבעות",
            "מעבר חלק בין שני צלילים",
        ],
        "correct": 0,
    },
    {
        "lesson": 3,
        "question": "עם אילו מושגים נהוג לקשר את יוהאן סבסטיאן באך?",
        "options": [
            "אופרה קומית ואוברטורה",
            "קונטרפונקט ופוגה",
            "סונטת פסנתר וסקרצו",
            "פואמה סימפונית ולידר",
        ],
        "correct": 1,
    },
    {
        "lesson": 3,
        "question": "באיזו תקופה מוזיקלית חי יוהאן סבסטיאן באך (1685–1750)?",
        "options": [
            "רנסאנס",
            "בארוק",
            "קלאסית",
            "רומנטית",
        ],
        "correct": 1,
    },
    {
        "lesson": 4,
        "question": "לאיזו קבוצה של כלי נשיפה מעץ שייך האבוב?",
        "options": [
            "ללא סופית (Air Jet)",
            "סופית בודדת",
            "סופית כפולה",
            "כלי פליז",
        ],
        "correct": 2,
    },
    {
        "lesson": 4,
        "question": "לאיזו קבוצה של כלי נשיפה מעץ שייך הקלרינט?",
        "options": [
            "ללא סופית (Air Jet)",
            "סופית בודדת",
            "סופית כפולה",
            "סופית משולשת",
        ],
        "correct": 1,
    },
    {
        "lesson": 4,
        "question": "באיזו קטגוריה נמנה החליל (חליל צד)?",
        "options": [
            "כלי נשיפה מעץ ללא סופית (Air Jet)",
            "כלי נשיפה מעץ עם סופית בודדת",
            "כלי נשיפה מעץ עם סופית כפולה",
            "כלי פליז טבעי",
        ],
        "correct": 0,
    },
    {
        "lesson": 4,
        "question": "כיצד מחולקים כלי ההקשה בתזמורת?",
        "options": [
            "לפי גודל הכלי בלבד",
            "לכלים עם פיץ׳ (צליל מוגדר) ולכלים ללא פיץ׳",
            "לכלים עם עץ ולכלים ממתכת בלבד",
            "לפי מיקומם על הבמה",
        ],
        "correct": 1,
    },
    {
        "lesson": 6,
        "question": "היכן ומתי נוצרה האופרה כסוגה מוזיקלית?",
        "options": [
            "בפריז בסוף המאה ה-17",
            "בוונציה בסביבות שנת 1600",
            "בווינה בתחילת המאה ה-19",
            "בברלין באמצע המאה ה-18",
        ],
        "correct": 1,
    },
    {
        "lesson": 6,
        "question": "מה ההבדל בין opera seria ל-opera buffa?",
        "options": [
            "opera seria היא אופרה רצינית, opera buffa היא אופרה קומית",
            "opera seria היא אופרה קומית, opera buffa היא אופרה רצינית",
            "opera seria משתמשת רק בכלי מיתר, opera buffa רק בכלי נשיפה",
            "שתיהן זהות, אלה שמות שונים לאותה סוגה",
        ],
        "correct": 0,
    },
    {
        "lesson": 6,
        "question": "מהי רצ׳יטטיב (Recitative) באופרה?",
        "options": [
            "קטע סולו מלודי ורגשי לסולן",
            "דיבור-בשירה להעברת עלילה ודיאלוגים",
            "קטע תזמורתי ללא זמרים",
            "קטע סיום של האופרה",
        ],
        "correct": 1,
    },
    {
        "lesson": 6,
        "question": "איזו מהיצירות הבאות היא אופרה של ג׳וזפה ורדי?",
        "options": [
            "לה בוהם",
            "טוסקה",
            "אאידה",
            "מאדאם באטרפליי",
        ],
        "correct": 2,
    },
    {
        "lesson": 6,
        "question": "איזו מהיצירות הבאות היא אופרה של ג׳אקומו פוצ׳יני?",
        "options": [
            "ריגולטו",
            "הטרובדור",
            "אותלו",
            "טורנדוט",
        ],
        "correct": 3,
    },
    {
        "lesson": 5,
        "question": "איזה כלי מקלדת קדם היסטורית לפסנתר המודרני?",
        "options": [
            "אקורדיון",
            "צ׳מבלו",
            "סקסופון",
            "תאורמין",
        ],
        "correct": 1,
    },
]


def assemble():
    # Only the שאלון*.docx files — skip תוכניה (syllabi).
    docx_files = sorted(p for p in ROOT.iterdir()
                        if p.suffix == ".docx" and p.name.startswith(("שאלון", "שאלות", "שיעור")))

    all_items = []
    for path in docx_files:
        items = extract_docx_questions(path, fallback_lesson=None)
        all_items.extend(items)

    # Dedupe by normalized key — prefer entries with a non-null `correct`.
    by_q: dict[str, dict] = {}
    for it in all_items:
        key = it["_key"]
        existing = by_q.get(key)
        if existing is None:
            by_q[key] = it
        else:
            if existing.get("correct") is None and it.get("correct") is not None:
                by_q[key] = it

    # Assign IDs and add lesson_title + source.
    per_lesson_counter: dict[int, int] = {}
    output = []
    for it in sorted(by_q.values(), key=lambda x: (x.get("lesson") or 99,)):
        lesson = it.get("lesson") or 0
        n = per_lesson_counter.get(lesson, 0) + 1
        per_lesson_counter[lesson] = n
        output.append({
            "id": f"L{lesson}Q{n:02d}",
            "lesson": lesson,
            "lesson_title": LESSON_TITLES.get(lesson, ""),
            "source": "bank",
            "source_file": it.get("source_file"),
            "question": it["question"],
            "options": it["options"],
            "correct": it.get("correct"),
        })
        # don't leak internal dedup key
        output[-1].pop("_key", None)

    # Append slide-derived questions.
    per_lesson_slides: dict[int, int] = {}
    for sq in SLIDE_QUESTIONS:
        lesson = sq["lesson"]
        n = per_lesson_slides.get(lesson, 0) + 1
        per_lesson_slides[lesson] = n
        output.append({
            "id": f"S{lesson}Q{n:02d}",
            "lesson": lesson,
            "lesson_title": LESSON_TITLES.get(lesson, ""),
            "source": "slides",
            "source_file": None,
            "question": sq["question"],
            "options": sq["options"],
            "correct": sq["correct"],
        })

    for q in output:
        exp = EXPLANATIONS.get(q["id"])
        if exp:
            q["explanation"] = exp

    return output


def main():
    output = assemble()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    from collections import Counter
    per_lesson = Counter((q["lesson"], q["source"]) for q in output)
    tbd = sum(1 for q in output if q["correct"] is None)
    print(f"Wrote {OUT_PATH} — {len(output)} questions")
    print(f"TBD correct: {tbd}")
    print("Breakdown:")
    for lesson in sorted(set(k[0] for k in per_lesson)):
        bank = per_lesson.get((lesson, "bank"), 0)
        slides = per_lesson.get((lesson, "slides"), 0)
        print(f"  lesson {lesson}: bank={bank} slides={slides}")


if __name__ == "__main__":
    main()
