from rapidfuzz import fuzz, process


def fuzzy_autocomplete(query: str, choices):
    if not query.strip():
        return choices[:25]
    results = process.extract(query, choices, scorer=fuzz.WRatio, limit=25, score_cutoff=50)
    return [value[0] for value in results]


# def fuzzy_find(query, choices):
#     result = process.extractOne(query, choices, scorer=fuzz.WRatio, score_cutoff=70)
#     return result[0] if result is not None else None


async def fuzzy_find_obj(query, db_query):
    obj = await db_query.find_one({'name': query})
    if obj is None:  # user gave us incorrect or incomplete name
        obj_choices = await db_query.find().to_list()
        obj_choices = {o: o.name for o in obj_choices}
        result = process.extractOne(query, obj_choices, scorer=fuzz.WRatio, score_cutoff=70)

        if result is None:
            raise ValueError(f"Can't find {query}!")

        obj = result[1]

    return obj
