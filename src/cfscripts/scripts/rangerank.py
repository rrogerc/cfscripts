from cfscripts.lib.rating import get_rating_changes_for_contest


def run(handle, contest_id, rank_range=200):
    contestants = get_rating_changes_for_contest(contest_id)
    goal_rating = -1
    for contestant in contestants:
        if contestant["handle"] == handle:
            goal_rating = contestant["oldRating"]
            break
    if goal_rating == -1:
        print("Handle not found in contest {}".format(contest_id))
        return
    relevants = []
    for contestant in contestants:
        rating = contestant["oldRating"]
        if abs(rating - goal_rating) <= rank_range:
            relevants.append(contestant)
    for i, rel in enumerate(relevants[::-1]):
        print(str(len(relevants) - i) + ": ", rel["handle"], "@", rel["oldRating"], "(actual rank:", str(rel["rank"])+")","  -->  ",rel["newRating"])
    rank = -1
    for i, rel in enumerate(relevants):
        if rel["handle"] == handle:
            rank = i + 1
    print()
    print("Showing results for", handle, "in", relevants[0]["contestName"], "(id: {})".format(contest_id))
    print("Your rating:", goal_rating)
    print("New rating:", relevants[rank-1]["newRating"])
    print("Compared to rating within the range: [{},{}]".format(goal_rating - rank_range, goal_rating + rank_range))
    print("Rank: ", rank, " / ", len(relevants))
    print()
