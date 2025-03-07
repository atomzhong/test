import random
import string
import time

from testbase.testcase import TestCase

from src.polaris_test_lib.polaris import PolarisServer
from src.polaris_test_lib.polaris_testcase import PolarisTestCase


class RatelimitScene05Check(PolarisTestCase):
    """
    Used to check ratelimit dataflow scene 05.

    Ratelimit type: Standalone ratelimit
    Target Service(Interface): default:RateLimitCalleeService:IN /business/info,/business/info/webclient
    Request traffic portrait: CALLER_SERVICE default REGEX RateLimitCaller.*
    Ratelimit conditions: Second-Level 5 times in 10 seconds
    Ratelimit Scheme: Fail Fast

    """
    owner = "atom"
    status = TestCase.EnumStatus.Ready
    priority = TestCase.EnumPriority.Normal
    timeout = 5

    def run_test(self):
        # ===========================
        self.get_console_token()
        self.polaris_server = PolarisServer(self.token, self.user_id)
        cmd_get_caller_port = "ps axu| grep Kona| grep ratelimit-caller| grep -v 'sh -c'| awk '{print $17}'|awk -F'=' '{print $2}'"
        ratelimit_caller_port, stderr = self.execute_shell(cmd_get_caller_port, timeout=10)
        ratelimit_caller_port = ratelimit_caller_port.replace("\n", "")
        ratelimit_callee_namespace = "default"
        ratelimit_callee_service = "RateLimitCalleeService"

        _random_str = ''.join(random.sample(string.ascii_letters + string.digits, 4))
        self.ratelimit_rule_name = "RatelimitSceneCheck-"

        self.service_ratelimit_rule_url = "http://" + self.polaris_server_http_restful_api_addr + PolarisServer.SERVICE_RATELIMIT_PATH
        _kwargs = {"url": self.service_ratelimit_rule_url, "ratelimit_rule_name": self.ratelimit_rule_name,
                   "limit": 10, "offset": 0}
        rsp = self.polaris_server.describe_service_ratelimit_rule(**_kwargs)
        polaris_code = rsp.json().get("code", None)
        self.assert_("Fail! No return except polaris code.", polaris_code == 200000)
        rule_id = rsp.json().get("rateLimits", None)[0]["id"]
        rule_name = rsp.json().get("rateLimits", None)[0]["name"]

        # ===========================
        self.start_step("Modify local service ratelimit rule.")

        srv_ratelimit_rule_failover = "FAILOVER_LOCAL"
        srv_ratelimit_rule_type = "LOCAL"

        rsp = self.polaris_server.modify_service_ratelimit_rule(
            self.service_ratelimit_rule_url, rule_id, rule_name, rule_type=srv_ratelimit_rule_type,
            ratelimit_namespace=ratelimit_callee_namespace, ratelimit_service=ratelimit_callee_service,
            ratelimit_method={"value": "/business/info,/business/info/webclient", "type": "IN"},
            ratelimit_arguments=[{"type": "CALLER_SERVICE",
                                  "key": "default",
                                  "value": {"type": "REGEX", "value": "RateLimitCaller.*"}}],
            ratelimit_amounts=[{"maxAmount": 5, "validDuration": "10s"}],
            ratelimit_regex_combine=True, ratelimit_action="REJECT", failover=srv_ratelimit_rule_failover,
            disable=False)

        polaris_code = rsp.json().get("code", None)
        self.assert_("Fail! No return except polaris code.", polaris_code == 200000)

        # ===========================
        self.start_step(
            "Wait 10s to request sct consumer to check provider ratelimit: /business/invoke->/bussiness/info will be limited.")
        time.sleep(10)
        cmd_curl = "curl -sv -H'test-header-key1:test-header-value1' 'http://127.0.0.1:%s/business/invoke'" % ratelimit_caller_port
        rsp, stderr = self.execute_shell(cmd_curl, timeout=15)
        self.assert_("Fail! No return except rate limit times.", rsp.count("TooManyRequests") >= 19)
        # ===========================
        self.start_step(
            "Request sct consumer to check provider ratelimit: /business/invoke/webclient->/bussiness/info/webclient will be limited.")
        cmd_curl = "curl -sv -H'test-header-key1:test-header-value2' 'http://127.0.0.1:%s/business/invoke/webclient'" % ratelimit_caller_port
        rsp, stderr = self.execute_shell(cmd_curl, timeout=15)
        self.assert_("Fail! No return except rate limit times.", rsp.count("TooManyRequests") >= 19)


if __name__ == '__main__':
    RatelimitScene05Check().debug_run()
