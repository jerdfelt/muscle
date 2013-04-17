from sqlalchemy import *

import muscle


@muscle.data_migration('foo', Column('bar', String(30)), Column('baz', Text))
def migrate_bar_to_baz(session, table, row):
    if row.baz is None and row.bar is not None:
        print 'migrating foo.bar to foo.baz'
        row.baz = row.bar
        # FIXME: Not really a fan of doing updates this way, but it appears
        # that making changes to the row here will not reflect as dirty in
        # the session
        session.execute(table.update().values(baz=row.bar)
                                      .where(table.c.id == row.id)
                                      .where(table.c.baz == None))
