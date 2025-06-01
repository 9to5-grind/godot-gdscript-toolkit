class Outer:
	class MyInnerTimer extends Timer:
		func _ready():
			start()

	func create_timer():
		var t = MyInnerTimer.new()
		add_child(t)
