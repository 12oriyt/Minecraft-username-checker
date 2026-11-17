import itertools
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


# ============================================================
# SETTINGS
# ============================================================

# Four letters only: aaaa -> zzzz
CHARACTERS = "abcdefghijklmnopqrstuvwxyz"

# Number of simultaneous requests.
# Keep this LOW to reduce rate limiting.
WORKERS = 3

# Delay between requests from each worker.
REQUEST_DELAY = 0.5

# How often progress is saved.
SAVE_EVERY = 100

# Files
AVAILABLE_FILE = "possibly_available.txt"
TAKEN_FILE = "taken.txt"
CHECKPOINT_FILE = "checkpoint.json"

# Mojang public profile lookup
API_URL = "https://api.minecraftservices.com/minecraft/profile/lookup/name/{}"

# Request timeout
TIMEOUT = 10


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "MinecraftUsernameChecker/1.0",
    "Accept": "application/json",
})


# ============================================================
# GENERATE NAMES
# ============================================================

def generate_names():
    """
    Generates:
    aaaa
    aaab
    aaac
    ...
    zzzz
    """
    for combination in itertools.product(CHARACTERS, repeat=4):
        yield "".join(combination)


# ============================================================
# CHECK NAME
# ============================================================

def check_name(username):
    url = API_URL.format(username)

    for attempt in range(6):
        try:
            response = session.get(
                url,
                timeout=TIMEOUT
            )

            # Profile exists
            if response.status_code == 200:
                return username, "TAKEN"

            # No profile found
            if response.status_code == 404:
                return username, "POSSIBLY_AVAILABLE"

            # Rate limited
            if response.status_code == 429:
                wait = min(60, 5 * (attempt + 1))

                print(
                    f"\n[!] Rate limited. Waiting {wait}s...",
                    flush=True
                )

                time.sleep(wait)
                continue

            # Server error
            if 500 <= response.status_code <= 599:
                time.sleep(3 * (attempt + 1))
                continue

            return username, f"HTTP_{response.status_code}"

        except requests.RequestException:
            time.sleep(2 * (attempt + 1))

    return username, "FAILED"


# ============================================================
# LOAD CHECKPOINT
# ============================================================

def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return 0

    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return int(data.get("index", 0))

    except Exception:
        return 0


def save_checkpoint(index):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "index": index,
                "total": 26 ** 4
            },
            f,
            indent=4
        )


# ============================================================
# LOAD EXISTING RESULTS
# ============================================================

def load_results():
    available = set()
    taken = set()

    if os.path.exists(AVAILABLE_FILE):
        with open(AVAILABLE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    available.add(name)

    if os.path.exists(TAKEN_FILE):
        with open(TAKEN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    taken.add(name)

    return available, taken


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(username, status):
    if status == "POSSIBLY_AVAILABLE":
        with open(AVAILABLE_FILE, "a", encoding="utf-8") as f:
            f.write(username + "\n")

    elif status == "TAKEN":
        with open(TAKEN_FILE, "a", encoding="utf-8") as f:
            f.write(username + "\n")


# ============================================================
# MAIN
# ============================================================

def main():

    total = 26 ** 4

    print("=" * 60)
    print("       MINECRAFT 4-LETTER USERNAME CHECKER")
    print("=" * 60)
    print()
    print(f"Characters : {CHARACTERS}")
    print(f"Combinations: {total:,}")
    print(f"Workers     : {WORKERS}")
    print()
    print("Results:")
    print(f"  {AVAILABLE_FILE}")
    print(f"  {TAKEN_FILE}")
    print()
    print("NOTE:")
    print("Names marked POSSIBLY_AVAILABLE are NOT guaranteed")
    print("to be immediately claimable on Minecraft.")
    print()

    available, taken = load_results()

    start_index = load_checkpoint()

    if start_index > 0:
        print(f"Resuming from combination #{start_index:,}")
        print()

    names = list(generate_names())

    # Don't check names already recorded
    checked = available | taken

    remaining = []

    for index, name in enumerate(names):

        if index < start_index:
            continue

        if name in checked:
            continue

        remaining.append((index, name))

    if not remaining:
        print("Everything has already been checked.")
        return

    print(f"Remaining: {len(remaining):,}")
    print()
    print("Starting...")
    print()

    checked_count = start_index

    # Process in small batches so memory stays reasonable
    batch_size = WORKERS * 5

    try:

        for batch_start in range(0, len(remaining), batch_size):

            batch = remaining[
                batch_start:
                batch_start + batch_size
            ]

            with ThreadPoolExecutor(
                max_workers=WORKERS
            ) as executor:

                futures = {
                    executor.submit(
                        check_name,
                        name
                    ): (index, name)
                    for index, name in batch
                }

                for future in as_completed(futures):

                    index, name = futures[future]

                    try:
                        username, status = future.result()

                    except Exception as e:
                        username = name
                        status = "FAILED"

                    checked_count += 1

                    if status == "POSSIBLY_AVAILABLE":

                        save_result(
                            username,
                            status
                        )

                        available.add(username)

                        print(
                            f"\n[+] POSSIBLY AVAILABLE: {username}",
                            flush=True
                        )

                    elif status == "TAKEN":

                        save_result(
                            username,
                            status
                        )

                        taken.add(username)

                    elif status == "FAILED":

                        print(
                            f"\n[!] Failed: {username}",
                            flush=True
                        )

                    percent = (
                        checked_count / total
                    ) * 100

                    print(
                        f"\rProgress: "
                        f"{checked_count:,}/{total:,} "
                        f"({percent:.2f}%) | "
                        f"Possible: {len(available):,}",
                        end="",
                        flush=True
                    )

                    if checked_count % SAVE_EVERY == 0:

                        save_checkpoint(
                            index + 1
                        )

            # Save after every batch
            if batch:
                save_checkpoint(
                    batch[-1][0] + 1
                )

            # Small cooldown between batches
            time.sleep(1)

    except KeyboardInterrupt:

        print()
        print()
        print("Stopped by user.")

        save_checkpoint(
            checked_count
        )

        print(
            "Progress saved. Run start.bat again to continue."
        )

        return

    print()
    print()
    print("=" * 60)
    print("SCAN FINISHED")
    print("=" * 60)
    print()
    print(
        f"Possible names found: {len(available):,}"
    )
    print(
        f"Results saved to: {AVAILABLE_FILE}"
    )
    print()


if __name__ == "__main__":
    main()