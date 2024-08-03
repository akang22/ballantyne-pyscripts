import pandas as pd
import streamlit
import unidecode
import codecs
import csv

import main

def unidecode_fallback(e):
    part = e.object[e.start:e.end]
    replacement = str(unidecode.unidecode(part) or '?')
    return (replacement, e.start + len(part))

codecs.register_error('unidecode_fallback', unidecode_fallback)

@streamlit.cache_data
def get_dfs():
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    people_df = pd.DataFrame([f"\"{a}\"" for a in [*main.get_corrupt_foreign_officials(), *main.get_tunisia_exposed(), *main.get_ukraine_exposed(), *main.get_consolidated_sanctions_names()]]).rename(columns={0: 'Individuals'})
    entities_df = pd.DataFrame([f"\"{a}\"" for a in [*main.get_consolidated_sanctions_entities(), *main.get_terrorism_groups_UN(), *main.get_list_of_entities_canada()]]).rename(columns={0: 'Entities'})
    return people_df, entities_df


@streamlit.cache_data
def get_encode(df):
    # encode pushing issues to unidecode.
    return df.to_csv(quoting=csv.QUOTE_NONE, escapechar="\\", index=False).encode('cp1252', errors='unidecode_fallback')

people_df, entities_df = get_dfs()

streamlit.title("AML Applet")

streamlit.header("Download")

streamlit.download_button(
    label="Download ATI.txt (individuals)",
    data=get_encode(people_df),
    file_name="ATI.txt",
    mime="text/plain"
)

streamlit.download_button(
    label="Download ATE.txt (entities)",
    data=get_encode(entities_df),
    file_name="ATE.txt",
    mime="text/plain"
)


streamlit.header("Individuals")
streamlit.dataframe(people_df, use_container_width=True)


streamlit.header("Entities")
streamlit.dataframe(entities_df, use_container_width=True)
