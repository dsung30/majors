import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)


def get_constants():
    constants = pd.read_csv("/Users/dsung/majors/espn_constants.csv")
    url = constants.iloc[0].value
    folder = constants.iloc[1].value
    par = int(constants.iloc[2].value)
    cutline = int(constants.iloc[3].value)
    return url, folder, par, cutline


def get_leaderboard(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_selector(".Table__TBODY")

        content = page.content()
        soup = BeautifulSoup(content, "html.parser")

        bodies = soup.find_all(class_="Table__TBODY")
        body = bodies[-1]

        headers = soup.find_all(class_="Table__THEAD")
        header = headers[-1]

        browser.close()

        return header, body


def get_draft_results(folder):
    file_loc = folder + "/draft_results.csv"
    draft_results = pd.read_csv(file_loc)
    return draft_results


def calc_score(draft_results, cutline, par, header, body, drop_low):
    player_dict = draft_results.set_index("player_name").to_dict()["owner"]
    owners = np.array(draft_results["owner"])
    owner_standings = dict.fromkeys(np.unique(owners))
    owner_standing_low_score = {owner: -10000 for owner in np.unique(owners)}
    rows = body.find_all("tr")
    tot_players = len(rows)
    col_names = header.find_all("th")
    col_dict = {}
    for i in range(len(col_names) - 1):
        if len(col_names[i].get_text()):
            col_dict[col_names[i].get_text()] = i
    full_standings = pd.DataFrame(
        columns=[
            "pos",
            "player",
            "status",
            "owner",
            "today",
            "thru",
            "score",
            "adj_score",
        ]
    )

    for k in owner_standings.keys():
        owner_standings[k] = 0

    for i in range(tot_players):
        row = rows[i]
        td = row.find_all("td")
        if len(td) == 1:
            pos = "----"
            player_name = "-----------------"
            status = td[0].get_text()
            owner = "-----"
            today = "--"
            thru = "--"
            score = "---"
            adj_score = "---"
            new_row = pd.DataFrame(
                [
                    {
                        "pos": pos,
                        "player": player_name,
                        "status": status,
                        "owner": owner,
                        "today": today,
                        "thru": thru,
                        "score": score,
                        "adj_score": adj_score,
                    }
                ]
            )

            full_standings = pd.concat([full_standings, new_row], ignore_index=True)
        else:
            player_name = td[col_dict["PLAYER"]].get_text()
            if player_name in player_dict.keys():
                owner = player_dict[player_name]
                pos = td[col_dict["POS"]].get_text()
                score = td[col_dict["SCORE"]].get_text()
                if score in ["CUT", "WD"]:
                    r1 = int(td[col_dict["R1"]].get_text())
                    r2 = int(td[col_dict["R2"]].get_text())
                    adj_score = r1 + r2 - 2 * par
                    status = "CUT"
                    score = "+" + str(adj_score) if adj_score > 0 else adj_score
                elif score == "DQ":
                    adj_score = 0
                    status = "DQ"
                    score = "DQ"
                else:
                    score_int = int(re.sub("[+]", "", score)) if score != "E" else 0
                    adj_score = min(score_int, cutline)
                    status = ""
                owner_standings[owner] = owner_standings[owner] + adj_score
                owner_standing_low_score[owner] = max(
                    owner_standing_low_score[owner], adj_score
                )
                try:
                    today = td[col_dict["TODAY"]].get_text()
                    thru = td[col_dict["THRU"]].get_text()
                except KeyError:
                    today = ""
                    thru = "F"

                adj_score = (
                    "+" + str(adj_score)
                    if adj_score > 0
                    else "E" if adj_score == 0 else adj_score
                )
                new_row = pd.DataFrame(
                    [
                        {
                            "pos": pos,
                            "player": player_name,
                            "status": status,
                            "owner": owner,
                            "today": today,
                            "thru": thru,
                            "score": score,
                            "adj_score": adj_score,
                        }
                    ]
                )

                full_standings = pd.concat([full_standings, new_row], ignore_index=True)
            else:
                continue

    if drop_low:
        for owner in owner_standings.keys():
            owner_standings[owner] = (
                owner_standings[owner] - owner_standing_low_score[owner]
            )

    owner_standings_df = pd.DataFrame(list(owner_standings.items()))
    owner_standings_df.columns = ["owner", "total"]
    owner_standings_df = owner_standings_df.sort_values(by="total", ascending=True)
    owner_standings_df.index = list(range(1, len(owner_standings_df) + 1))
    owner_standings_df["total"] = owner_standings_df["total"].apply(
        lambda x: "+" + str(x) if x > 0 else "E" if x == 0 else str(x)
    )
    return full_standings, owner_standings_df


def main():
    drop_low = True
    url, folder, par, cutline = get_constants()
    header, body = get_leaderboard(url)
    draft_results = get_draft_results(folder)
    full_standings, owner_standings = calc_score(
        draft_results, cutline, par, header, body, drop_low
    )
    print("\n\n************************* INDIVIDUAL SCORE *************************\n")
    print(full_standings)
    if drop_low:
        print(
            "\n\n************************* TEAM SCORE (High Score Dropped) *************************\n"
        )
    else:
        print(
            "\n\n**************************** TEAM SCORE ****************************\n"
        )
    print(owner_standings)
    print("\n\n")


if __name__ == "__main__":
    main()
