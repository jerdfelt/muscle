from sqlalchemy import *


def expand(engine, desired):
    ddl_c = engine.dialect.ddl_compiler(engine.dialect, None)

    # Load current schema via reflection
    current = MetaData()
    current.reflect(engine)

    changed = False

    # Check if there are new tables that need to be created
    current_tables = set(current.tables.keys())
    desired_tables = set(desired.tables.keys())

    missing_tables = desired_tables - current_tables
    if missing_tables:
        # Create all of the new databases
        for name in missing_tables:
            print 'Creating table', name
            table = desired.tables[name]
            table.create(engine)
            changed = True

    if changed:
        # Reload current schema
        current.reflect(engine)

    changed = False

    # Check if there are new columns for any of the tables
    for tablename, dtable in desired.tables.iteritems():
        ctable = current.tables[tablename]

        ccolumns = dict((c.name, c) for c in ctable.columns)
        dcolumns = dict((c.name, c) for c in dtable.columns)

        # Create all of the new columns
        missing_columns = set(dcolumns.keys()) - set(ccolumns.keys())
        for name in missing_columns:
            print 'Creating column %s.%s' % (tablename, name)
            column = dcolumns[name]

            colspec = ddl_c.get_column_specification(column)
            sql = 'ALTER TABLE %s ADD %s' % (tablename, colspec)
            engine.execute(sql)
            changed = True

    if changed:
        # Reload current schema
        current.reflect(engine)

    return current


def contract(engine, desired):
    # Load current schema via reflection
    current = MetaData()
    current.reflect(engine)

    changed = False

    # Check if there are old columns for any of the tables
    for tablename, dtable in desired.tables.iteritems():
        ctable = current.tables[tablename]

        ccolumns = dict((c.name, c) for c in ctable.columns)
        dcolumns = dict((c.name, c) for c in dtable.columns)

        # Create all of the new columns
        extra_columns = set(ccolumns.keys()) - set(dcolumns.keys())
        for name in extra_columns:
            print 'Dropping column %s.%s' % (tablename, name)

            sql = 'ALTER TABLE %s DROP %s' % (tablename, name)
            engine.execute(sql)
            changed = True

    if changed:
        # Reload current schema
        # FIXME: reflect doesn't remove columns that no longer exist?
        #current.reflect(engine)
        current = MetaData()
        current.reflect(engine)

    changed = False

    # Check if there are old tables that need to be dropped
    current_tables = set(current.tables.keys())
    desired_tables = set(desired.tables.keys())

    extra_tables = current_tables - desired_tables
    if extra_tables:
        # Drop all of the old databases
        for name in extra_tables:
            print 'Dropping table', name
            table = current.tables[name]
            table.drop(engine)
            changed = True

    if changed:
        # Reload current schema
        current.reflect(engine)

    return current
