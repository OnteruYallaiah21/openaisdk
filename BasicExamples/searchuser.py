import json
from pathlib import Path
from difflib import get_close_matches

#data/email_data
def load_data():
    current_dir = Path(__file__).resolve().parent.parent
    json_path = current_dir / "data" /"email_data" /"email.json"

    with open(json_path, "r") as f:
        return json.load(f)


def search_user(query: str, threshold: float = 0.6):
    """
    Search user by name or email with:
    - Partial match (like SQL %query%)
    - Fuzzy match (handles typos)
    """

    data = load_data()
    query = query.lower()
    results = []

    for email, users in data.items():
        for user in users:
            name = user.get("name", "").lower()
            email_lower = email.lower()

            # 🔹 1. Partial match (LIKE %query%)
            if query in name or query in email_lower:
                results.append(user)
                continue

            # 🔹 2. Fuzzy match (typo handling)
            name_words = name.split()
            possible_matches = name_words + [email_lower]

            matches = get_close_matches(query, possible_matches, n=1, cutoff=threshold)

            if matches:
                results.append(user)

    return results


# ================= TEST =================
if __name__ == "__main__":
    print("\n--- Search Results ---")

    queries = ["hari"]

    for q in queries:
        print(f"\nQuery: {q}")
        res = search_user(q)
        for r in res:
            print(f"results is =>{r} and  the datatype is => {type(r)}")