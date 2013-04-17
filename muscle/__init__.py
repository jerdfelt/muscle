from sqlalchemy import *
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import mapper, object_mapper


_migrations = []


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


# Simple helper
def dictify(row):
    return dict((k, getattr(row, k))
                for k in object_mapper(row).columns.keys())


def _load_listener(target, context):
    # FIXME: This could be optimized to create a list of only the data
    # migrations that still need to be run by inspecting the schema on
    # load
    for table, srccol, dstcol, func in _migrations:
        if target.__table__.name != table:
            continue

        table = target.__table__

        if hasattr(table.c, srccol.name) and hasattr(table.c, dstcol.name):
            # FIXME: Check schema of srccol and dstcol and make sure they
            # match
            func(context.session, table, target)


def data_migration(table, srccol, dstcol):
    """Add data migration function"""
    def inner(func):
        _migrations.append((table, srccol, dstcol, func))
        return func

    return inner


# FIXME: It's probably not necessary to explicitly call this patch()
# func. We could do the same incrementally in data_migration() above.
def patch(current, desired):
    for name, dtable in desired.iteritems():
        if not hasattr(dtable, '__table__'):
            continue

        tablename = dtable.__table__.name

        if tablename not in current.tables:
            continue

        ctable = current.tables[tablename]

        ccolumns = dict((c.name, c) for c in ctable.columns)
        dcolumns = dict((c.name, c) for c in dtable.metadata.tables[tablename].columns)

        # Patch desired schema with rows not deleted yet
        missing_columns = set(ccolumns.keys()) - set(dcolumns.keys())
        for name in missing_columns:
            setattr(dtable, name, ccolumns[name].copy())

        # Setup load event for this class
        event.listen(dtable, 'load', _load_listener)
