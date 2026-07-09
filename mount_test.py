from telescope import Telescope
from core.ascom.interface import MountCapability

scope = Telescope()

scope.connect()

input("Enterで切断")

caps = scope.get_capabilities()
print("CanMoveAxis:", MountCapability.CAN_MOVE_AXIS in caps)
print("CanPulseGuide:", MountCapability.CAN_PULSE_GUIDE in caps)

scope.disconnect()