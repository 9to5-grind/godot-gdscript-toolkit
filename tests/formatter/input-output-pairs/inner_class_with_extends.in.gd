extends Node

class MyInnerTimer extends Timer:
    func _init():
        var t = Timer.new()
        add_child(t)