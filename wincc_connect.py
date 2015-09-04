import click
import traceback
import logging

from wincc import wincc, WinCCException, do_alarm_report,\
    do_batch_alarm_report, do_operator_messages_report, WinCCHosts,\
    get_host_by_name
from alarm import alarm_query_builder
from tag import tag_query_builder, print_tag_logging, plot_tag_records
from interactive import InteractiveModeWinCC, InteractiveMode
from operator_messages import om_query_builder
from helper import tic, datetime_to_str_without_ms
from report import generate_alarms_report
from datetime import datetime
from mssql import mssql


class StringCP1252ParamType(click.ParamType):
    """String Param Type for click to curb with annoying windows cmd shell
    encoding problems. German Umlaute are not correctly read from cmd line
    if Parameter Type is click.String
    """
    name = 'text'

    def convert(self, value, param, ctx):
        if isinstance(value, bytes):
            enc = 'cp1252'
            value = value.decode(enc)
            return value
        return value

    def __repr__(self):
        return 'STRING_CP1252'

STRING_CP1252 = StringCP1252ParamType()


@click.group()
@click.option('--debug', default=False, is_flag=True, help='Turn on debug mode. Will print some debug messages.')
def cli(debug):
    if debug:
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option('--host', '-h', default='127.0.0.1', help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')    
@click.option('--wincc-provider', '-w', default=False, is_flag=True, help='Use WinCCOLEDBProvider.1 instead of SQLOLEDB.1')
def interactive(host, database, wincc_provider):
    if wincc_provider:
        # interactive_mode_wincc(host, database)
        shell = InteractiveModeWinCC(host, database)
        shell.run()
    else:
        shell = InteractiveMode(host, database)
        shell.run()


@cli.command()
@click.argument('tagid', nargs=-1)
@click.argument('begin_time', nargs=1)
@click.option('--end-time', '-e', default='', help='Can be absolute (see begin-time) or relative 0000-00-01[ 12:00:00[.000]]')
@click.option('--timestep', '-t', default=0, help='Group result in timestep long sections. Time in seconds.')
@click.option('--mode', '-m', default='first', help="Optional mode. Can be first, last, min, max, avg, sum, count, and every mode with an '_interpolated' appended e.g. first_interpolated.")
@click.option('--host', '-h', default='', help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')
@click.option('--utc', default=False, is_flag=True, help='Activate utc time. Otherwise local time is used.')
@click.option('--show', '-s', default=False, is_flag=True, help="Don't actually query the db. Just show what you would do.")
@click.option('--hostname', '-n', default='',
              help='Hostname (will be looked up in hosts.sav)')
def tag(tagid, begin_time, end_time, timestep, mode, host, database, utc, show, hostname):
    """Parse user friendly tag query and assemble userunfriendly wincc query"""
    if hostname:
        h = get_host_by_name(hostname)
        host = h.host_address
        database = h.database
    elif host:
        pass
    else:
        print('Either hostname or host must be specified. Quitting.')
        return

    query = tag_query_builder(tagid, begin_time, end_time, timestep, mode, utc)
    if show:
        print(query)
        return

    toc = tic()
    try:
        w = wincc(host, database)
        w.connect()
        w.execute(query)

        if w.rowcount():
            print_tag_logging(w.fetchall())
            # for rec in w.fetchall():
            #    print rec

        print("Fetched data in {time}.".format(time=round(toc(), 3)))

    except Exception as e:
        print(e)
        print(traceback.format_exc())
    finally:
        w.close()


@cli.command()
@click.argument('tagid', nargs=-1)
@click.argument('begin_time', nargs=1)
@click.option('--end-time', '-e', default='', help='Can be absolute (see begin-time) or relative 0000-00-01[ 12:00:00[.000]]')
@click.option('--timestep', '-t', default=0, help='Group result in timestep long sections. Time in seconds.')
@click.option('--mode', '-m', default='first', help="Optional mode. Can be first, last, min, max, avg, sum, count, and every mode with an '_interpolated' appended e.g. first_interpolated.")
@click.option('--host', '-h', default='', help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')
@click.option('--utc', default=False, is_flag=True, help='Activate utc time. Otherwise local time is used.')
@click.option('--show', '-s', default=False, is_flag=True, help="Don't actually query the db. Just show what you would do.")
@click.option('--hostname', '-n', default='',
              help='Hostname (will be looked up in hosts.sav)')
def tag2(tagid, begin_time, end_time, timestep, mode, host, database, utc, show, hostname):
    """Parse user friendly tag query and assemble userunfriendly wincc query"""
    if hostname:
        h = get_host_by_name(hostname)
        host = h.host_address
        database = h.database
    elif host:
        pass
    else:
        print('Either hostname or host must be specified. Quitting.')
        return

    query = tag_query_builder(tagid, begin_time, end_time, timestep, mode, utc)
    if show:
        print(query)
        return

    toc = tic()
    try:
        w = wincc(host, database)
        w.connect()
        w.execute(query)

        records = w.create_tag_records()
        print("Fetched data in {time}.".format(time=round(toc(), 3)))
        # print(tags)
        # tags.plot()
        for record in records:
            print(record)
        #plot_tag_records(records)

    except Exception as e:
        print(e)
        print(traceback.format_exc())
    finally:
        w.close()


@cli.command()
@click.argument('begin_time')
@click.option('--end-time', '-e', default='',
              help='Can be absolute (see begin-time) or relative 0000-00-01[ 12:00:00[.000]]')
@click.option('--text', default='', type=STRING_CP1252,
              help='Message text or part of message text.')
@click.option('--host', '-h', default='', help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')
@click.option('--utc', default=False, is_flag=True,
              help='Activate utc time. Otherwise local time is used.')
@click.option('--show', '-s', default=False, is_flag=True,
              help="Don't actually query the db. Just show what you would do.")
@click.option('--state', default='', type=click.STRING,
              help="State condition e.g. '=2' or '>1'")
@click.option('--report', '-r', default=False, is_flag=True,
              help="Print html alarm report")
@click.option('--report-hostname', '-rh', default='',
              help="Host description to be printed on report.")
@click.option('--hostname', '-n', default='',
              help='Hostname (will be looked up in hosts.sav)')
def alarms(begin_time, end_time, text, host, database, utc, show, state,
           report, report_hostname, hostname):
    """Read alarms from given host in given time."""
    if hostname:
        h = get_host_by_name(hostname)
        host = h.host_address
        database = h.database
        report_hostname = h.descriptive_name
    elif host:
        pass
    else:
        print('Either hostname or host must be specified. Quitting.')
        return

    query = alarm_query_builder(begin_time, end_time, text, utc, state)

    if show:
        print(query)
        return

    try:
        toc = tic()
        w = wincc(host, database)
        w.connect()
        w.execute(query)

        if report:
            alarms = w.create_alarm_record()
            if report_hostname:
                host_description = report_hostname
            else:
                host_description = host
            if not end_time:
                end_time = datetime_to_str_without_ms(datetime.now())
            generate_alarms_report(alarms, begin_time, end_time,
                                   host_description, text)
            print(unicode(alarms))
        else:
            w.print_alarms()

        print("Fetched data in {time}.".format(time=round(toc(), 3)))
    except WinCCException as e:
        print(e)
        print(traceback.format_exc())
    finally:
        w.close()


@cli.command()
@click.argument('begin_time')
@click.option('--end-time', '-e', default='', help='Can be absolute (see begin-time) or relative 0000-00-01[ 12:00:00[.000]]')
@click.option('--text', default='', type= STRING_CP1252,help='Message text or part of message text.')
@click.option('--host', '-h', prompt=True, help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')
@click.option('--utc', default=False, is_flag=True, help='Activate utc time. Otherwise local time is used.')
@click.option('--show', '-s', default=False, is_flag=True, help="Don't actually query the db. Just show what you would do.")
def operator_messages(begin_time, end_time, text, host, database, utc, show):
    """Query db for operator messages."""
    query = om_query_builder(begin_time, end_time, text, utc)
    if show:
        print(query)
        return

    try:
        toc = tic()
        w = wincc(host, database)
        w.connect()
        w.execute(query)
        w.print_operator_messages()
        print("Fetched data in {time}.".format(time=round(toc(), 3)))
    except WinCCException as e:
        print(e)
        print(traceback.format_exc())
    finally:
        w.close()


@cli.command()
@click.argument('tagname')
@click.argument('hostname')
# @click.option('--host', '-h', prompt=True, help='Hostname')
# @click.option('--database', '-d', default='',
# help='Initial Database (Catalog).')
# @click.option('--hostname', '-n', prompt=True,
#              help='Hostname (will be looked up in hosts.sav)')
def tagid_by_name(tagname, hostname):
    """Search hosts db for tag entries matching the given name.
    Return tagid.
    """
    h = get_host_by_name(hostname)
    host = h.host_address
    database = h.database[:-1]

    try:
        toc = tic()
        mssql_conn = mssql(host, database)
        mssql_conn.connect()
        mssql_conn.execute("SELECT TLGTAGID, VARNAME FROM PDE#TAGs WHERE "
                           "VARNAME LIKE '%{name}%'".format(name=tagname))
        if mssql_conn.rowcount():
            for rec in mssql_conn.fetchall():
                print rec
        print("Fetched data in {time}.".format(time=round(toc(), 3)))
    except Exception as e:
        print(e)
    finally:
        mssql_conn.close()


@cli.command()
@click.argument('begin_time')
@click.argument('end_time')
@click.option('--host', '-h', prompt=True, help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')
@click.option('--cache', is_flag=True, default=False, help='Cache alarms (pickle).')
@click.option('--use-cached', is_flag=True, default=False, help='Use cached alarms')
def alarm_report(begin_time, end_time, host, database, cache, use_cached):
    """Print report of alarms for given host in given time."""
    do_alarm_report(begin_time, end_time, host, database, cache, use_cached)


@cli.command()
@click.argument('begin_time')
@click.argument('end_time')
@click.option('--host', '-h', prompt=True, help='Hostname')
@click.option('--database', '-d', default='', help='Initial Database (Catalog).')
@click.option('--cache', is_flag=True, default=False, help='Cache alarms (pickle).')
@click.option('--use-cached', is_flag=True, default=False, help='Use cached alarms')
def operator_messages_report(begin_time, end_time, host, database, cache, use_cached):
    """Print report of operator messages for given host in given time."""
    do_operator_messages_report(begin_time, end_time, host, database, cache, use_cached)


@cli.command()
@click.argument('begin_day')
@click.argument('end_day')
@click.option('--host', '-h', help='Hostname')
@click.option('--database', '-d', help='Initial Database (Catalog).')
@click.option('--hostname', '-n', default='', help='Hostname (will be looked up in hosts.sav)')
def batch_report(begin_day, end_day, host, database, hostname):
    """Print a report for each day starting from begin_day to end_day."""
    if hostname:
        hosts = WinCCHosts()
        h = hosts.get_host(hostname)
        if h:
            host = h.host_address
            database = h.database
            host_desc = h.descriptive_name
            logging.info('Successfully loaded %s %s %s %s.',
                         hostname, host, database, host_desc)
    elif host:
        host_desc = ''
    else:
        print('Either hostname or host must be specified. Quitting.')
        return

    if not database:
        logging.info('Database name not given. Trying to fetch it.')
        wincc_ = wincc(host, '')
        database = wincc_.fetch_wincc_database_name()
        wincc_.close()

    do_batch_alarm_report(begin_day, end_day, host, database, host_desc)


@cli.command()
@click.argument('hostname')
@click.argument('begin_day')
@click.argument('end_day')
@click.option('--timestep', '-t', help='Time interval [day|week|month].')
def alarm_report2(hostname, begin_day, end_day, timestep):
    """Generate report(s) for known host."""
    hosts = WinCCHosts()
    host = hosts.get_host(hostname)
    host_address = host.host_address
    database = host.database
    host_desc = host.descriptive_name

    do_batch_alarm_report(begin_day, end_day, host_address,
                          database, host_desc, timestep)


@cli.command()
@click.argument('hostname')
def parameters(hostname):
    """Connect to host and retrieve parameter list."""
    host = get_host_by_name(hostname)
    mssql_conn = mssql(host.host_address, host.database[:-1])
    mssql_conn.connect()
    params = mssql_conn.create_parameter_record()
    mssql_conn.close()
    print(params)

if __name__ == "__main__":
    cli()
