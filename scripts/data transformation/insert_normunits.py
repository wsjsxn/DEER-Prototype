#!/usr/bin/env python
# coding: utf-8

"""Optional tool to replace normalizing units in files like sim_annual.csv.

Features:
* Copies sizing information from alternate result query into sim_annual.csv.
* Requires python >= 3.7.1, pandas, xlrd

Prerequisite:
    * sim_annual.csv (from data transformation tool)
    * results-sizing-agg.csv (from alternate result query)

Usage:
    cd "C:/DEER-Prototypes-EnergyPlus/residential measures/SWHC001-05 Wall Furnace/SWHC001-05 Wall Furnace_SFm"
    python "C:/DEER-Prototypes-EnergyPlus/scripts/data transformation/insert_normunits.py"

Changelog
    * 2024-01-19 Python script to enable replacing normunits in sim_annual files.
    * 2024-03-20 Command line and usage documentation

@Author: Nicholas Fette, Behzad Salimian Rizi
@Date: 2024-01-19
"""

# Import all necessary libraries
import pandas as pd
from pathlib import Path
import os
from argparse import ArgumentParser

def insert_normunits1(
        filename_sizing_agg,
        filename_simannual,
        output_sizing,
        output_simannual,
        sizing_column,
        normunit,
        sizing_multiplier,
        measure_name
    ):

    #%%

    # Assumes this file is located at "DEERROOT/scripts/data transformation/insert_normunits.py"
    TRANSFORM_PATH = Path(os.path.dirname(__file__))
    DEERROOT = TRANSFORM_PATH / '../..'
    MEASURELIST_PATH = TRANSFORM_PATH / 'DEER_EnergyPlus_Modelkit_Measure_list.xlsx'

    # %%
    # 1. Read master workbook for measure / tech list
    df_master = pd.read_excel(MEASURELIST_PATH, sheet_name='Measure_list', skiprows=4)
    # Specify the name of the measure(e.g. 'Wall Furnace')
    df_measure = df_master[df_master['Measure (general name)'] == measure_name]
    MEASURE_GROUP_NAMES = list(df_measure['Measure Group Name'].unique())

    #generate unique list of measure names
    MEASURES = list(df_measure['Measure (general name)'].unique())

    #%%
    # 2. Expand measure list with climate zones and filenames
    s_bldgloc = pd.Series(['CZ01', 'CZ02', 'CZ03', 'CZ04', 'CZ05', 'CZ06', 'CZ07', 'CZ08',
        'CZ09', 'CZ10', 'CZ11', 'CZ12', 'CZ13', 'CZ14', 'CZ15', 'CZ16'],
        name='BldgLoc')
    tech_frame1 = (
        df_measure
        [['PreTechID', 'BldgType', 'Story-flag', 'BldgVint', 'BldgHVAC','Measure Group Name','Common_PreTechID']]
        .rename(columns={'PreTechID':'TechID','Common_PreTechID':'CommonTechID'})
    )
    tech_frame2 = (
        df_measure
        [['StdTechID', 'BldgType', 'Story-flag', 'BldgVint', 'BldgHVAC','Measure Group Name','Common_StdTechID']]
        .rename(columns={'StdTechID':'TechID','Common_StdTechID':'CommonTechID'})
    )
    tech_frame3 = (
        df_measure
        [['MeasTechID', 'BldgType', 'Story-flag', 'BldgVint', 'BldgHVAC','Measure Group Name','Common_MeasTechID']]
        .rename(columns={'MeasTechID':'TechID','Common_MeasTechID':'CommonTechID'})
    )
    df_mapper = pd.concat([tech_frame1, tech_frame2, tech_frame3]).drop_duplicates()
    df_mapper = df_mapper.merge(s_bldgloc, how='cross')
    # Filenames represent 'instance-out.sql' as found in e.g. result-summary.csv.
    filename_template = '{BldgLoc}/{Measure Group Name}/{CommonTechID}/instance-out.sql'
    tech_filenames = df_mapper.apply(lambda x: filename_template.format(**x), axis=1)
    df_mapper['File Name'] = tech_filenames

    #%%
    # 3. Lookup tables for NumStor and NumBldg
    # Create CZ:VintYear dictionary based on prototype definitions
    # BldgType, Story-flag, BldgVint, VintYear, BldgLoc, numstor, weight
    df_numstor2 = pd.read_excel(TRANSFORM_PATH / 'NumStor2.xlsx', sheet_name='NumStor')
    df_numbldgs = pd.DataFrame([('DMo',2),('MFm',24),('SFm',2)],columns=['BldgType','numbldgs'])

    #%%
    # 4. Read sizing info and change from 'File Name' to desired index columns.

    df_myunits_raw = pd.read_csv(filename_sizing_agg)
    # Assume first columns is 'File Name', other columns are data.
    data_columns = df_myunits_raw.columns[1:]
    # Clean up filenames.
    df_myunits_raw['File Name'] = df_myunits_raw['File Name'].str.removeprefix('runs/')
    print(df_myunits_raw.shape)
    # Append label columns from Measure List
    df_myunits_raw = df_myunits_raw.merge(df_mapper, on='File Name')
    print(df_myunits_raw.shape)
    # Align the NumStor weights to this table.
    df_myunits_raw = (
        df_myunits_raw
        .merge(df_numstor2[['BldgType','BldgVint','BldgLoc','Story-flag','weight']],
            on=['BldgType','BldgVint','BldgLoc','Story-flag'])
    )
    weights = (
        df_myunits_raw[['BldgType','BldgVint','BldgLoc','Story-flag']]
        .merge(df_numstor2, on=['BldgType','BldgVint','BldgLoc','Story-flag'])
        ['weight']
    )
    #weights = (
    #    df_numstor2.set_index(['BldgType','BldgVint','BldgLoc','Story-flag'])
    #    .reindex(index=df_myunits_raw[['BldgType','BldgVint','BldgLoc','Story-flag']])
    #    ['weight']
    #)

    # Multiply the data columns by weights.
    # Note that weights already add up to 1 in next step.
    df_myunits_weighted = df_myunits_raw.copy()
    #df_myunits_weighted[data_columns] = df_myunits_weighted[data_columns].mul(weights, axis=0)
    df_myunits_weighted[data_columns] = df_myunits_weighted[data_columns].mul(df_myunits_raw['weight'], axis=0)
    df_myunits_weighted.to_csv('myunits_weighted.csv')
    # Aggregate by label columns and sum weighted values in data columns.
    df_myunits = (
        df_myunits_weighted
        .groupby(['TechID', 'BldgType', 'BldgVint', 'BldgLoc', 'BldgHVAC'])
        [data_columns.to_list()+['weight']]
        .sum()
    )

    print('Saving',output_sizing)
    df_myunits.to_csv(output_sizing)

    # %%
    # 5. Read 'sim_annual' and overwrite numunits.

    index_cols = ['TechID', 'BldgType', 'BldgVint', 'BldgLoc', 'BldgHVAC']

    df_mysim_annual = pd.read_csv(filename_simannual, index_col=index_cols)
    df_myunits_sim = df_myunits.reindex(df_mysim_annual.index)
    sizing_divisor = (
        df_myunits_sim.reset_index()
        .merge(df_numbldgs, on=['BldgType'])
        .set_index(index_cols)
        ['numbldgs']
    )
    df_mysim_annual['normunit'] = normunit
    df_mysim_annual['numunits'] = df_myunits_sim[sizing_column] * sizing_multiplier / sizing_divisor

    print('Saving',output_simannual)
    df_mysim_annual.to_csv(output_simannual)

    print('Done.')

def test():
    # User inputs

    # Specify the original files
    filename_sizing_agg = 'results-sizing-agg.csv'
    filename_simannual = 'sim_annual.csv'

    # Specify the files to output from this script
    output_sizing = 'results-per-dwelling.csv'
    output_simannual = 'sfm_annual_withunits.csv'

    # Specify the column name to use for normalizing units.
    sizing_column = 'Coil:Heating:Fuel Design Size Nominal Capacity (W)'
    normunit = 'CapOut-kBtuh'

    # Specify a multipler, e.g. for a unit conversion.
    kbtuh_per_watt = 3.412141633
    sizing_multiplier = 1/kbtuh_per_watt

    measure_name = 'Wall Furnace'

    # Now, just run the script.
    insert_normunits1(
        filename_sizing_agg,
        filename_simannual,
        output_sizing,
        output_simannual,
        sizing_column,
        normunit,
        sizing_multiplier,
        measure_name
    )

def main():
    # Command line version
    parser = ArgumentParser()
    parser.add_argument('filename_sizing_agg',type=Path,help='The alternate result file, default results-sizing-agg.csv.',default='results-sizing-agg.csv')
    parser.add_argument('filename_simannual',type=Path,help='The original sim_annual file, default sim_annual.csv.',default='sim_annual.csv')
    parser.add_argument('output_sizing',type=Path,help='The alternate result file, default results-per-dwelling.csv.',default='results-per-dwelling.csv')
    parser.add_argument('output_simannual',type=Path,help='The alternate result file, default sim_annual_withunits.csv.',default='sim_annual_withunits.csv')
    parser.add_argument('sizing_column',type=str,help='The column name to read for new normalizing units value.')
    parser.add_argument('normunit',type=str,help='The label to write for new normalizing units.')
    parser.add_argument('sizing_multiplier',type=float,help='The alternate result file, default results-sizing-agg.csv.',default=1.0)
    parser.add_argument('measure_name',help='The measure name as it appears in Measure_list.xlsx. ')
    args = parser.parse_args()
    insert_normunits1(
        args.filename_sizing_agg,
        args.filename_simannual,
        args.output_sizing,
        args.output_simannual,
        args.sizing_column,
        args.normunit,
        args.sizing_multiplier,
        args.measure_name
    )

if __name__ == "__main__":
    # Select testing or command line mode here.
    #test()
    main()