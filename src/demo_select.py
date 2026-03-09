from typing import List, Dict

def select_demo_records_balanced(records: List[Dict], n_each: int = 10) -> List[Dict]:
    q21 = [r for r in records if str(r.get("question_id")) in ("Q21", "21")]
    q28 = [r for r in records if str(r.get("question_id")) in ("Q28", "28")]

    take_q21 = q21[:n_each]
    take_q28 = q28[:n_each]

    demo = take_q21 + take_q28

    target = 2 * n_each
    if len(demo) < target:
        need = target - len(demo)
        q21_rest = q21[len(take_q21):]
        q28_rest = q28[len(take_q28):]
        demo += (q21_rest + q28_rest)[:need]

    return demo
