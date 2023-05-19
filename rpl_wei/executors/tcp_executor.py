"""Handling execution for steps in the RPL-SDL efforts"""
from rpl_wei.core.data_classes import Module, Step

def wei_tcp_callback(step: Step, **kwargs):
    from socket import socket

    module: Module = kwargs["step_module"]

    sock = socket.bind(module.config["tcp_address"], module.config["tcp_port"])
    msg = {
        "action_handle": step.command,
        "action_vars": step.args,
    }

    sock.send(str(msg).encode())
    tcp_response = sock.read().decode()
    tcp_response = eval(tcp_response)
    action_response = tcp_response.get('action_response')
    action_msg = tcp_response.get('action_msg')
    action_log = tcp_response.get('action_log')
    #TODO: assert all of the above. deal with edge cases?
    return action_response, action_msg, action_log
