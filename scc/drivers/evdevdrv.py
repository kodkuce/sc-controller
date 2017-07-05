"""
Universal driver for gamepads managed by evdev.

Handles no devices by default. Instead of trying to guess which evdev device
is a gamepad and which user actually wants to be handled by SCC, list of enabled
devices is read from config file.
"""

from scc.controller import Controller
from scc.constants import SCButtons
from scc.config import Config
from scc.poller import Poller
from collections import namedtuple
import evdev
import struct, os, time, binascii, logging
log = logging.getLogger("evdev")


EvdevControllerInput = namedtuple('EvdevControllerInput',
	'seq buttons ltrig rtrig '
	'lpad_x lpad_y lstick_x lstick_y rstick_x rstick_y'
)


class EvdevController(Controller):
	"""
	Wrapper around evdev device.
	To keep stuff simple, this class tries to provide and use same methods
	as SCController class does.
	"""
	
	def __init__(self, daemon, device, config):
		Controller.__init__(self)
		self.device = device
		self.config = config
		self.poller = daemon.get_poller()
		self.poller.register(self.device.fd, self.poller.POLLIN, self.input)
		self.device.grab()
		self._id = self._generate_id()
		self._state = EvdevControllerInput( *[0] * len(EvdevControllerInput._fields) )
		
		self._evdev_to_button = {}
		if "buttons" in config:
			for x, value in config["buttons"].iteritems():
				try:
					keycode = int(x)
					sc = getattr(SCButtons, value)
					self._evdev_to_button[keycode] = sc
				except: pass
	
	
	def close(self):
		try:
			self.device.ungrab()
		except: pass
		self.device.close()
	
	
	def get_type(self):
		return "evdev"
	
	
	def get_id(self):
		return self._id
	
	
	def _generate_id(self):
		"""
		ID is generated as 'ev' + upper_case(hex(crc32(device name + X)))
		where 'X' starts as 0 and increases as controllers with same name are
		connected.
		"""
		magic_number = 0
		id = None
		while id is None or id in _evdevdrv._used_ids:
			crc32 = binascii.crc32("%s%s" % (self.device.name, magic_number))
			id = "ev%s" % (hex(crc32).upper().strip("-0X"),)
			magic_number += 1
		_evdevdrv._used_ids.add(id)
		return id
	
	
	def get_id_is_persistent(self):
		return True
	
	
	def __repr__(self):
		return "<Evdev %s>" % (self.device.name,)
	
	
	def input(self, *a):
		new_state = self._state
		for event in self.device.read():
			if event.type == evdev.ecodes.EV_KEY:
				if event.code in self._evdev_to_button:
					if event.value:
						b = new_state.buttons | self._evdev_to_button[event.code]
						new_state = new_state._replace(buttons=b)
					else:
						b = new_state.buttons & ~self._evdev_to_button[event.code]
						new_state = new_state._replace(buttons=b)
		if new_state is not self._state:
			# Something got changed
			old_state, self._state = self._state, new_state
			if self.mapper:
				self.mapper.input(self, time.time(), old_state, new_state)
	
	
	def apply_config(self, config):
		# TODO: This?
		pass
	
	
	def disconnected(self):
		# TODO: This!
		pass
	
	
	# def configure(self, idle_timeout=None, enable_gyros=None, led_level=None):
	
	
	def set_led_level(self, level):
		# TODO: This?
		pass
	
	
	def set_gyro_enabled(self, enabled):
		# TODO: This, maybe.
		pass
	
	
	def turnoff(self):
		"""
		Exists to stay compatibile with SCController class as evdev controller
		typically cannot be shut down like this.
		"""
		pass
	
	
	def get_gyro_enabled(self):
		""" Returns True if gyroscope input is currently enabled """
		return False
	
	
	def feedback(self, data):
		""" TODO: It would be nice to have feedback... """
		pass


class EvdevDriver(object):
	def __init__(self):
		self._daemon = None
		self._devices = {}
		self._used_ids = set()
	
	
	def handle_new_device(self, dev, config):
		controller = EvdevController(self._daemon, dev, config)
		self._devices[dev] = controller
		self._daemon.add_controller(controller)
		log.debug("Evdev device added: %s", dev.name)
	
	
	def start(self):
		c = Config()
		for fname in evdev.list_devices():
			dev = evdev.InputDevice(fname)
			if dev.name in c['evdev_devices']:
				self.handle_new_device(dev, c['evdev_devices'][dev.name])
	
	
	def mainloop(self):
		pass

# Just like USB driver, EvdevDriver is process-wide singleton
_evdevdrv = EvdevDriver()

def init(daemon):
	_evdevdrv._daemon = daemon
	# daemon.on_daemon_exit(_evdevdrv.on_exit)
	daemon.add_mainloop(_evdevdrv.mainloop)

def start(daemon):
	_evdevdrv.start()
