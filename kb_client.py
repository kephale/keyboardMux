import os
import dbus
import evdev
import keymap
from time import sleep

HID_DBUS = 'org.yaptb.btkbservice'
HID_SRVC = '/org/yaptb/btkbservice'


class Kbrd:
    """
    Take the events from a physically attached keyboard and send the
    HID messages to the keyboard D-Bus server.
    """
    def __init__(self, sendCB):
        self.target_length = 6
        self.mod_keys = 0b00000000
        self.pressed_keys = []
        self.have_kb = False
        self.dev = None
        self.sendCB = sendCB
        #self.bus = dbus.SystemBus()
        #self.btkobject = self.bus.get_object(HID_DBUS,
        #                                     HID_SRVC)
        #self.btk_service = dbus.Interface(self.btkobject,
        #                                  HID_DBUS)

        # TODO auto detect atreus
        print("searching for atreus")
        # atreus_event = self.get_atreus_id()
        atreus_event = 7
        print(f"atreus found at event {atreus_event}")
        
        self.wait_for_keyboard(event_id=atreus_event)

    def get_atreus_id(self):

        listing = os.listdir("/sys/class/input")

        listing = [path for path in listing if "event" in path]

        names = []
        atreus_id = -1
        for path in listing:
            filename = f"/sys/class/input/{path}/device/name"
            with open(filename) as f:
                name = f.readlines()
                names.append(name)
                if "Keyboardio Atreus Keyboard" in name:
                    atreus_id = len(names)
                    print(filename)

        return atreus_id
        
        
    def wait_for_keyboard(self, event_id=7):
        """
        Connect to the input event file for the keyboard.
        Can take a parameter of an integer that gets appended to the end of
        /dev/input/event
        :param event_id: Optional parameter if the keyboard is not event0
        """
        while not self.have_kb:
            try:
                # try and get a keyboard - should always be event0 as
                # we're only plugging one thing in
                self.dev = evdev.InputDevice('/dev/input/event{}'.format(
                    event_id))
                self.have_kb = True
            except OSError:
                print('Keyboard not found, waiting 3 seconds and retrying')
                sleep(3)
            print('found a keyboard')

    def update_mod_keys(self, mod_key, value):
        """
        Which modifier keys are active is stored in an 8 bit number.
        Each bit represents a different key. This method takes which bit
        and its new value as input
        :param mod_key: The value of the bit to be updated with new value
        :param value: Binary 1 or 0 depending if pressed or released
        """
        bit_mask = 1 << (7-mod_key)
        if value: # set bit
            self.mod_keys |= bit_mask
        else: # clear bit
            self.mod_keys &= ~bit_mask

    def update_keys(self, norm_key, value):
        if value < 1:
            self.pressed_keys.remove(norm_key)
        elif norm_key not in self.pressed_keys:
            self.pressed_keys.insert(0, norm_key)
        len_delta = self.target_length - len(self.pressed_keys)
        if len_delta < 0:
            self.pressed_keys = self.pressed_keys[:len_delta]
        elif len_delta > 0:
            self.pressed_keys.extend([0] * len_delta)

    @property
    def state(self):
        """
        property with the HID message to send for the current keys pressed
        on the keyboards
        :return: bytes of HID message
        """
        return [0xA1, 0x01, self.mod_keys, 0, *self.pressed_keys]

    def send_keys(self):
        #print("Sending: ", self.state)
        self.sendCB(self.state)
        #self.btk_service.send_keys(self.state)

    def event_loop(self):
        """
        Loop to check for keyboard events and send HID message
        over D-Bus keyboard service when they happen
        """
        print('Listening...')
        for event in self.dev.read_loop():
            # only bother if we hit a key and its an up or down event
            #print(event)
            if event.type == evdev.ecodes.EV_KEY and event.value < 2:
                key_str = evdev.ecodes.KEY[event.code]
                mod_key = keymap.modkey(key_str)
                #print(f"key {key_str} {mod_key}")
                if mod_key > -1:
                    self.update_mod_keys(mod_key, event.value)
                else:
                    self.update_keys(keymap.convert(key_str), event.value)
            self.send_keys()


if __name__ == '__main__':
    print('Setting up keyboard')
    kb = Kbrd()

    print('starting event loop')
    kb.event_loop()
