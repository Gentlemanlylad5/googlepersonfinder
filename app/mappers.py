from mapreduce.operation.counters import Increment
from mapreduce.operation.db import Put

def make_prefixed_increment(prefix):
    return lambda name: Increment(prefix + '.' + name)

def count_person(person):
    inc = make_prefixed_increment(person.subdomain + '.person')
    yield inc('all')
    yield inc('is_expired=' + repr(person.is_expired))
    if not person.is_expired:
        yield inc('expired=False')
        yield inc('original_domain=' + (person.original_domain or ''))
        yield inc('sex=' + (person.sex or ''))
        yield inc('home_country=' + (person.home_country or ''))
        yield inc('photo=' + (person.photo_url and 'present' or ''))
        yield inc('num_notes=%d' % len(person.get_notes()))
        yield inc('status=' + (person.latest_status or ''))
        yield inc('found=' + repr(person.latest_found))
        yield inc('linked_persons=%d' % len(person.get_linked_persons()))

def count_note(note):
    inc = make_prefixed_increment(note.subdomain + '.note')
    yield inc('all')
    yield inc('is_expired=' + repr(note.is_expired))
    if not note.is_expired:
        yield inc('not_expired')
        yield inc('original_domain=' + (note.original_domain or ''))
        yield inc('status=' + (note.status or ''))
        yield inc('found=' + repr(note.found))
        if note.linked_person_record_id:
            yield inc('linked_person')
        if note.last_known_location:
            yield inc('last_known_location')

def add_property(entity):
    """If the specified property is not present, set it to its default value."""
    params = context.get().mapreduce_spec.mapper.params
    name = params['property_name']
    if getattr(entity, name, None) is None:
        setattr(entity, name, entity.properties()[name].default_value())
        yield Put(entity)
        yield Increment('written')

def add_is_expired_property(entity):
    """If the is_expired property is not present, set it to False."""
    if not entity.is_expired:
        if entity.is_expired is not False:
            entity.is_expired = False
            yield Put(entity)
            yield Increment('written')
