import pkg_resources
import numpy as np
import pandas as pd


def load_food_metadata():
    """
    Return: a dataframe containing Global FoodOmics ontology and metadata.
    """
    stream = pkg_resources.resource_stream(__name__, 'data/foodomics_multiproject_metadata.txt')
    gfop_metadata = pd.read_csv(stream, sep='\t')
    # Remove trailing whitespace
    gfop_metadata = gfop_metadata.apply(lambda col: col.str.strip()
                                        if col.dtype == 'object' else col)
    return gfop_metadata


def get_sample_types(simple_complex=None):
    """
    Return:
        Global FoodOmics ontology containing only simple, only complex, or all foods.
    Args:
        simple_complex (string): one of 'simple', 'complex', or 'None'.
                                 Simple foods are single ingredients while complex foods contain multiple ingredients.
                                 'None' will return both simple and complex foods.
    """
    gfop_metadata = load_food_metadata()
    if simple_complex is not None:
        gfop_metadata = gfop_metadata[gfop_metadata['simple_complex'] == simple_complex]
    col_sample_types = [f'sample_type_group{i}' for i in range(1, 7)]
    return (gfop_metadata[['filename', *col_sample_types]]
            .set_index('filename'))


def get_file_food_counts(gnps_network, sample_types, all_groups, some_groups,
                         filename, level):
    """
    Generate food counts for an individual sample in a study dataset.
    A count indicates a spectral match between a reference food and the study sample.

    Args:
        gnps_network (dataframe): tsv file generated from classical molecular networking
                                  with study dataset(s) and reference dataset.
        sample_types (dataframe): obtained using get_sample_types().
        all_groups (list): can contain 'G1', 'G2' to denote study spectrum files.
        some_groups (list): can contain 'G3', 'G4' to denote reference spectrum files.
        filename (string): name of study sample mzXML file.
        level (integer): indicates the level of the food ontology to use.
                         One of 1, 2, 3, 4, 5, or 6
    Return:
        A vector
    Examples:
        get_file_food_counts(gnps_network = gnps_network,
                             sample_types = sample_types,
                             all_groups = ['G1'],
                             some_groups = ['G4'],
                             filename = 'sample1.mzXML',
                             level = 5)
    """
    # Select GNPS job groups.
    groups = {f'G{i}' for i in range(1, 7)}
    groups_excluded = groups - set([*all_groups, *some_groups])
    df_selected = gnps_network[
        (gnps_network[all_groups] > 0).all(axis=1) &
        (gnps_network[some_groups] > 0).any(axis=1) &
        (gnps_network[groups_excluded] == 0).all(axis=1)].copy()
    df_selected = df_selected[
        df_selected['UniqueFileSources'].apply(lambda cluster_fn:
            any(fn in cluster_fn for fn in filename))]
    filenames = (df_selected['UniqueFileSources'].str.split('|')
                 .explode())
    # Select food hierarchy levels.
    sample_types = sample_types[f'sample_type_group{level}'] # remove this line to do file-level
    # Match the GNPS job results to the food sample types.
    sample_types_selected = sample_types.reindex(filenames)
    sample_types_selected = sample_types_selected.dropna()
    # Discard samples that occur less frequent than water (blank).
    water_count = (sample_types_selected == 'water').sum()
    sample_counts = sample_types_selected.value_counts()
    sample_counts_valid = sample_counts.index[sample_counts > water_count]
    sample_types_selected = sample_types_selected[
        sample_types_selected.isin(sample_counts_valid)]
    # Get sample counts at the specified level.
    return sample_types_selected.value_counts()


def get_dataset_food_counts(gnps_network, metadata, filename_col,
                            sample_types, all_groups, some_groups,
                            level):
    """
    Generate a table of food counts for a study dataset.

    Args:
        gnps_network (string): path to tsv file generated from classical molecular.
                               networking with study dataset(s) and reference dataset.
        metadata (string): path to sample metadata (comma- or tab-separated) file.
                           Must contain a column with mzXML file names that match those used in the molecular networking job.
        filename_col (string): name of column header containing file names.
        sample_types (string): one of 'simple', 'complex', or 'None'.
                               Simple foods are single ingredients while complex foods contain multiple ingredients.
                               'None' will return both simple and complex foods.
        all_groups (list): can contain 'G1', 'G2' to denote study spectrum files.
        some_groups (list): can contain 'G3', 'G4' to denote reference spectrum files.
        level (integer): indicates the level of the food ontology to use.
                         One of 1, 2, 3, 4, 5, or 6.
    Return:
        A data frame
    Examples:
        get_dataset_food_counts(gnps_network = 'METABOLOMICS-SNETS-V2-07f85565-view_all_clusters_withID_beta-main.tsv',
                                metadata = 'sample_metadata.csv',
                                filename_col = 'filenames',
                                sample_types = 'simple',
                                all_groups = ['G1'],
                                some_groups = ['G4'],
                                level = 5)
    """
    food_counts, filenames = [], []
    gnps_network = pd.read_csv(gnps_network, sep='\t')
    sample_types = get_sample_types(sample_types)
    delim = ',' if metadata.endswith('.csv') else '\t'
    metadata = pd.read_csv(metadata, sep=delim)
    metadata = metadata.dropna(subset=[filename_col])
    for filename in metadata[filename_col]:
        file_food_counts = get_file_food_counts(gnps_network, sample_types, all_groups, some_groups, [filename], level)
        if len(file_food_counts) > 0:
            food_counts.append(file_food_counts)
            filenames.append(filename)
    food_counts = (pd.concat(food_counts, axis=1, sort=True).fillna(0).astype(int).T)
    food_counts.index = pd.Index(filenames, name='filename')
    return food_counts