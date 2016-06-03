#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_serialization
------------------

Tests for `cookiecutter.serialization` module.
"""

from __future__ import unicode_literals

import pytest

from cookiecutter.serialization import \
    SerializationFacade, JsonSerializer, AbstractSerializer
from cookiecutter.exceptions import UnknownSerializerType, \
    BadSerializedStringFormat, InvalidSerializerType, InvalidType


@pytest.fixture
def get_context():
    """
    helper method to get a bunch of context objects
    """
    context = {
        "my_key": "my_val"
    }

    context2 = {
        "my_key2": "my_val2"
    }

    json_serialized = JsonSerializer().serialize(context).decode()

    return {
        'object': context,
        'object2': context2,
        'json': 'json|' + json_serialized + '$'
    }


@pytest.fixture
def get_serializers():
    """
    helper method to get a bunch of serializers
    """
    class FakeSerializer(object):
        def serialize(self, subject):
            return b'serialized'

        def deserialize(self, string):
            return {}

    class DummySerializer(AbstractSerializer):
        def _do_serialize(self, subject):
            return ' serialized text' if 'my_key2' in subject else 'serialized'

        def _do_deserialize(self, string):
            return get_context()['object2'] if 'serialized text' in string \
                else get_context()['object']

    return {
        'fake': FakeSerializer,
        'dummy': DummySerializer
    }


class TestSerialization(object):

    def test_default_serialize(self):
        """
        serialize a context object with the default available serializer
        """
        assert get_context()['json'] == SerializationFacade().serialize(
            get_context()['object'])

    def test_default_deserialize(self):
        """
        deserialize a context string with the default available serializer
        """

        assert get_context()['object'] == SerializationFacade().deserialize(
            get_context()['json'])

    def test_not_registered_serializer_during_serialization(self):
        """
        ensure a non registered serializer cannot be called during
        serialization
        """
        with pytest.raises(UnknownSerializerType) as excinfo:
            _type = 'not_registered'
            SerializationFacade().serialize(
                get_context()['object'], _type)

            assert _type in excinfo.message

    def test_not_registered_serializer_during_deserialization(self):
        """
        ensure a non registered serializer cannot be called during
        deserialization
        """
        with pytest.raises(UnknownSerializerType) as excinfo:
            _type = 'not_registered'
            serialized = _type + '|somestring$'
            SerializationFacade().deserialize(serialized)

            assert _type in excinfo.message

    def test_register_serializer(self):
        """
        register a custom serializer class
        """
        _type = 'dummy'
        context = get_context()['object']
        kclass = get_serializers()[_type]
        facade = SerializationFacade()
        facade.register(_type, kclass)
        expected = _type + '|' + kclass().serialize(context).decode() + '$'

        assert expected == facade.serialize(context, _type)
        assert context == facade.deserialize(expected)

    def test_register_serializer_accepts_object(self):
        """
        register a custom serializer instance
        """
        _type = 'dummy'
        context = get_context()['object']
        serializer = get_serializers()[_type]()
        facade = SerializationFacade()
        facade.register(_type, serializer)
        expected = _type + '|' + serializer.serialize(context).decode() + '$'

        assert expected == facade.serialize(context, _type)

    def test_serializer_api_check(self):
        """
        enforce the given serializer to extends AbstractSerializer
        """
        with pytest.raises(InvalidType) as excinfo:
            SerializationFacade().register(
                'fake', get_serializers()['fake']
            )

        assert 'AbstractSerializer' in excinfo.value.message

    def test_get_serialization_type(self):
        """
        get the type of the current serializer
        """
        _type = 'dummy'
        context = get_context()['object']
        serializer = get_serializers()[_type]()
        facade = SerializationFacade()
        facade.register(_type, serializer)
        serialized = _type + '|' + serializer.serialize(context).decode() + '$'

        assert 'json' == facade.get_type()
        facade.deserialize(serialized)
        assert _type == facade.get_type()

    def test_existing_serializer_can_be_replaced(self):
        """
        overwrite an existing serializer with a custom one
        """
        _type = 'json'
        context = get_context()['object']
        serializer = get_serializers()['dummy']()
        facade = SerializationFacade()
        facade.register(_type, serializer)
        expected = _type + '|' + serializer.serialize(context).decode() + '$'

        assert expected == facade.serialize(context, _type)

    def test_serializer_list_can_be_set_at_facade_initialization(self):
        """
        initialize the serialization facade with a bunch of serializers
        """
        _type = 'dummy'
        context = get_context()['object']
        serializer = get_serializers()[_type]()
        dict = {
            _type: serializer
        }
        facade = SerializationFacade(dict)
        expected = _type + '|' + serializer.serialize(context).decode() + '$'

        assert expected == facade.serialize(context, _type)

    def test_missing_type_in_serialized_string(self):
        """
        ensure that a string passed to the deserialize method contains the
        serializer type
        """
        expected = 'Serialized string should be of the form'
        with pytest.raises(BadSerializedStringFormat) as excinfo:
            SerializationFacade().deserialize('{"my_key": "my_val"}')

        assert expected in excinfo.value.message

    def test_serializer_valid_types(self):
        """
        ensure a serializer type contains only some allowed characters
        """
        context = get_context()['object']
        serializer = get_serializers()['dummy']()

        valid_types = {
            'v_a-l.idTyPe0123456789': serializer,
            '_type': serializer,
            'Type': serializer
        }
        facade = SerializationFacade(valid_types)

        not_valid_types = [
            '-type',
            '.type',
            '_.type',
            '9type',
            '_9type',
            'typ|e',
            'typ:e',
            'typ!e',
        ]

        for _type in valid_types:
            expected = _type + '|' + \
                serializer.serialize(context).decode() + '$'
            assert expected == facade.serialize(context, _type)

        for _type in not_valid_types:
            with pytest.raises(InvalidSerializerType):
                facade.register(_type, serializer)

    def test_deserialize_the_last_serialized_string_found(self):
        """
        deserialize method should treat only the last serialized string part
        """
        serializer = get_serializers()['dummy']()
        part1 = serializer.serialize(get_context()['object']).decode()
        part2 = serializer.serialize(get_context()['object2']).decode()
        serialized = 'dummy text dummy|' + part1 + '$ ' \
            'another dummy text dummy|' + part2 + '$'
        facade = SerializationFacade({
            'dummy': serializer
        })

        assert get_context()['object2'] == facade.deserialize(serialized)
