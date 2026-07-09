from telescope import Telescope

scope = Telescope()

scope.connect()

input("Enterで切断")

print(scope.CanMoveAxis(0))
print(scope.CanMoveAxis(1))

scope.disconnect()