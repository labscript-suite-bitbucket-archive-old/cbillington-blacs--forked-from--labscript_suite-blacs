#####################################################################
#                                                                   #
# /plugins/__init__.py                                              #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the program BLACS, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import

import os
import sys
import logging
import importlib
from types import MethodType
from collections import defaultdict
from labscript_utils.labconfig import LabConfig
from blacs import BLACS_DIR
PLUGINS_DIR = os.path.join(BLACS_DIR, 'plugins')

default_plugins = ['connection_table', 'general', 'theme']

logger = logging.getLogger('BLACS.plugins')

DEFAULT_PRIORITY = 10


class BasePlugin(object):
    """Base class for plugins, implementing default methods"""
    def __init__(self, initial_settings):
        self.menu = None
        self.notifications = None
        self.initial_settings = initial_settings
        self.BLACS = None

    def get_menu_class(self):
        """Return a subclass of BaseMenu, specifying the details of a menu for this
        plugin that should be added to the menu bar"""
        return None

    def get_notification_classes(self):
        """Return a list of subclasses of BaseNotification for types of notification
        that may or may not be visible at any time."""
        return []

    def get_settings_classes(self):
        """TODO docstring"""
        return []

    def get_callbacks(self):
        """This method should return a dictionary mapping callback names to callables or
        Callback objects."""
        return {}

    def set_menu_instance(self, menu):
        """Called by BLACS to set the menu instance, an instance of the class returned
        by get_menu_class. Subclasses should not need to override this method."""
        self.menu = menu

    def set_notification_instances(self, notifications):
        """Called by BLACS to set the notification instances, which are instances of the
        classes returned by get_notification_classes. Subclasses should not need to
        override this method. notifications is a dictionary of instances, keyed by
        class."""
        self.notifications = notifications

    def plugin_setup_complete(self, BLACS):
        """Called by BLACS when it has finished instantiating settings, menus,
        notifications etc. Subclasses should override this method to restore save data
        (as passed into __init__ as initial_settings) to the places in the GUI it
        belongs, and to set up plugin-specific functionality such as starting threads or
        adding widgets to the BLACS interface."""
        self.BLACS = BLACS

    def get_save_data(self):
        """Return a dictionary of data that should be saved from one run of BLACS to the
        next. At startup, data saved this way will be passed as initial_settings to
        __init__()"""
        return {}

    def close(self):
        """Perform any required shutdown before BLACS closes."""
        pass


class BaseSettings(object):
    """Base class for settings objects, implementing default methods. Subclasses of
    BasePlugin should return a list of subclasses of BaseSettings from their
    get_settings_classes() method."""
    pass


class BaseMenu(object):
    """Base class for menus, implementing default methods. Subclasses of BasePlugin
    should return a list of subclasses of BaseMenu objects from their get_menu_class()
    method."""
    def __init__(self,BLACS):
        self.BLACS = BLACS
        # close_notification_func is a method that will be called when the user
        # dismisses a notification. Subclasses may set it here, but existing plugins
        # tend to set it at runtime from the plugin object, possibly pointing to a
        # callable that is not a method of the menu object. It should be None if there
        # are no notification classes returned by the plugin's
        # get_notification_classes() method.
        self.close_notification_func = None

    def get_menu_items(self):
        """Return a dictionary {'name': <menu_name>, 'menu_items' <items>}, where items
        is a list of dictionaries for items that should be in the menu, each of the form
        {'name': <item name>, 'action': <callable>, 'icon' <icon_name>} describing the
        appearance of a menu item and what callable should be run when it is
        activated"""
        return {
            'name': 'Example plugin menu',
            'menu_items': [
                {
                    'name': 'example item',
                    'action': lambda: None,
                    'icon': ':/qtutils/fugue/document--pencil',
                }
            ],
        }


class BaseNotification(object):
    pass


class Callback(object):
    """Class wrapping a callable. At present only differs from a regular
    function in that it has a "priority" attribute - lower numbers means
    higher priority. If there are multiple callbacks triggered by the same
    event, they will be returned in order of priority by get_callbacks"""
    def __init__(self, func, priority=DEFAULT_PRIORITY):
        self.priority = priority
        self.func = func

    def __get__(self, instance, class_):
        """Make sure our callable binds like an instance method. Otherwise
        __call__ doesn't get the instance argument."""
        if instance is None:
            return self
        else:
            return MethodType(self, instance)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class callback(object):
    """Decorator to turn a function into a Callback object. Presently
    optional, and only required if the callback needs to have a non-default
    priority set"""
    # Instantiate the decorator:
    def __init__(self, priority=DEFAULT_PRIORITY):
        self.priority = priority
    # Call the decorator
    def __call__(self, func):
        return Callback(func, self.priority)


def get_callbacks(name):
    """Return all the callbacks for a particular name, in order of priority"""
    import __main__
    BLACS = __main__.app
    callbacks = []
    for plugin in BLACS.plugins.values():
        try:
            plugin_callbacks = plugin.get_callbacks()
            if plugin_callbacks is not None:
                if name in plugin_callbacks:
                    callbacks.append(plugin_callbacks[name])
        except Exception as e:
            logger.exception('Error getting callbacks from %s.' % str(plugin))
            
    # Sort all callbacks by priority:
    callbacks.sort(key=lambda callback: getattr(callback, 'priority', DEFAULT_PRIORITY))
    return callbacks


exp_config = LabConfig()
if not exp_config.has_section('BLACS/plugins'):
    exp_config.add_section('BLACS/plugins')

modules = {}
for module_name in os.listdir(PLUGINS_DIR):
    if os.path.isdir(os.path.join(PLUGINS_DIR, module_name)) and module_name != '__pycache__':
        # is it a new plugin?
        # If so lets add it to the config
        if not module_name in [name for name, val in exp_config.items('BLACS/plugins')]:
            exp_config.set('BLACS/plugins', module_name, str(module_name in default_plugins))

        # only load activated plugins
        if exp_config.getboolean('BLACS/plugins', module_name):
            try:
                module = importlib.import_module('blacs.plugins.'+module_name)
            except Exception:
                logger.exception('Could not import plugin \'%s\'. Skipping.'%module_name)
            else:
                modules[module_name] = module
