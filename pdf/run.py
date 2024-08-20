# -*- coding: utf-8 -*-
"""
Created on Mon Jun 24 12:56:19 2024

@author: AllanPankratz
"""

import tabula 
import pandas 

pdf_path="ETF_Handbook.pdf"

tabula.read_pdf(pdf_path, multiple_tables=False, format="csv", pages="all", output_path="first_table3.csv")
tabula.convert_into(pdf_path, "first_table2.csv", output_format="csv", pages = 'all')

