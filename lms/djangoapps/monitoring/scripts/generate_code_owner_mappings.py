"""
This script generates code owner mappings for monitoring LMS.

Sample usage::

    python lms/djangoapps/monitoring/scripts/generate_code_owner_mappings.py --app-csv "edx-platform Apps Ownership.csv"

Sample CSV input::

    Path,owner.squad
    ./common/djangoapps/xblock_django,team-red
    ./openedx/core/djangoapps/xblock,team-red
    ./lms/djangoapps/badges,team-blue

Sample output::

    # Copy results into appropriate config yml file.
    CODE_OWNER_MAPPINGS:
      team-blue:
      - badges
      team-red:
      - xblock_django
      - openedx.core.djangoapps.xblock

"""
import os
import re
import csv
import click


@click.command()
@click.option(
    '--app-csv',
    help="File name of .csv file with edx-platform app ownership details.",
    required=True
)
def main(app_csv):
    """
    Reads CSV of ownership data and outputs config.yml setting to system.out.

    Expected CSV format:

        Path,owner.squad\n
        ./lms/templates/oauth2_provider,team-red\n
        ./openedx/core/djangoapps/user_authn,team-blue\n
        ...

    Final output only includes paths which might contain views.

    """
    csv_data = None
    with open(app_csv, 'r') as file:
        csv_data = file.read()
    reader = csv.DictReader(csv_data.splitlines())

    team_to_paths_map = {}
    for row in reader:
        path = row.get('Path')
        team = row.get('owner.squad')

        # add paths that may have views
        may_have_views = re.match(r'.*djangoapps', path) or re.match(r'[./]*openedx\/features', path)
        # remove cms (studio) paths and tests
        may_have_views = may_have_views and not re.match(r'.*(\/tests\b|cms\/).*', path)

        if may_have_views:
            path = path.replace('./', '')  # remove ./ from beginning of path
            path = path.replace('/', '.')  # convert path to dotted module name

            # skip catch-alls to ensure everything is properly mapped
            if path in ('common,djangoapps', 'lms.djangoapps', 'openedx.core.djangoapps', 'openedx.features'):
                continue

            if team not in team_to_paths_map:
                team_to_paths_map[team] = []
            team_to_paths_map[team].append(path)

    print('# Do not hand edit CODE_OWNER_MAPPINGS. Generated by {}'.format(os.path.basename(__file__)))
    print('CODE_OWNER_MAPPINGS:')
    for team, path_list in sorted(team_to_paths_map.items()):
        print("  {}:".format(team))
        path_list.sort()
        for path in path_list:
            print("  - {}".format(path))


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
