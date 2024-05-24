import streamlit
import main

streamlit.title("AML Applet")
streamlit.header("People")
streamlit.dataframe([*main.get_corrupt_foreign_officials(), *main.get_tunisia_exposed(), *main.get_ukraine_exposed(), *main.get_consolidated_sanctions_names()], use_container_width=True)

streamlit.header("Entities")
streamlit.dataframe([*main.get_consolidated_sanctions_entities(), *main.get_terrorism_groups_UN(), *main.get_list_of_entities_canada()], use_container_width=True)
