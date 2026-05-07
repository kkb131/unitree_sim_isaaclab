"""
DG-5F DDS communication class — single 20-DoF hand using HandCmd_/HandState_
(unitree_hg). Pattern adapted from `dds/dex3_dds.py` (dual-hand) collapsed to
a single hand on topics rt/dg5f/state and rt/dg5f/cmd.

Joint convention (DDS index 0..19, finger-major — see action_provider mapping):
  [0..3]  finger 1 joint 1..4
  [4..7]  finger 2 joint 1..4
  [8..11] finger 3 joint 1..4
  [12..15]finger 4 joint 1..4
  [16..19]finger 5 joint 1..4

Per build guide §3.2: HandCmd_/HandState_.motor_state/motor_cmd is a
variable-length sequence; default factory pre-allocates 7 slots, so we
re-init to 20 explicitly.
"""

from typing import Any, Dict, Optional

from dds.dds_base import DDSObject
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_, HandState_
from unitree_sdk2py.idl.default import (
    unitree_hg_msg_dds__HandState_,
    unitree_hg_msg_dds__MotorState_,
)


N_MOTORS = 20


class DG5FDDS(DDSObject):
    """Single-hand 20-DoF DG-5F DDS — publishes rt/dg5f/state, subscribes rt/dg5f/cmd."""

    def __init__(self, node_name: str = "dg5f"):
        if hasattr(self, "_initialized"):
            return

        super().__init__()
        self.node_name = node_name

        # Pre-allocate a 20-slot HandState_ message; the factory defaults to 7 slots.
        self.hand_state = unitree_hg_msg_dds__HandState_()
        self.hand_state.motor_state = [
            unitree_hg_msg_dds__MotorState_() for _ in range(N_MOTORS)
        ]

        self.state_publisher: Optional[ChannelPublisher] = None
        self.cmd_subscriber: Optional[ChannelSubscriber] = None

        self._initialized = True

        # 20 motor × 5 fields × ~10 bytes ≈ 1000 bytes; allow JSON overhead.
        self.setup_shared_memory(
            input_shm_name="isaac_dg5f_state",
            input_size=2048,
            output_shm_name="isaac_dg5f_cmd",
            output_size=2048,
        )

        print(f"[{self.node_name}] DG-5F DDS node initialized (20 motors)")

    # ------------------------------------------------------------------ #
    # Publisher / subscriber setup (called by DDSManager.start_publishing) #
    # ------------------------------------------------------------------ #

    def setup_publisher(self) -> bool:
        try:
            self.state_publisher = ChannelPublisher("rt/dg5f/state", HandState_)
            self.state_publisher.Init()
            print(f"[{self.node_name}] state publisher initialized (rt/dg5f/state)")
            return True
        except Exception as e:
            print(f"dg5f_dds [{self.node_name}] state publisher init failed: {e}")
            return False

    def setup_subscriber(self) -> bool:
        try:
            self.cmd_subscriber = ChannelSubscriber("rt/dg5f/cmd", HandCmd_)
            self.cmd_subscriber.Init(lambda msg: self.dds_subscriber(msg, ""), 32)
            print(f"[{self.node_name}] command subscriber initialized (rt/dg5f/cmd)")
            return True
        except Exception as e:
            print(f"dg5f_dds [{self.node_name}] command subscriber init failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Subscriber callback (DDS → SHM)                                    #
    # ------------------------------------------------------------------ #

    def dds_subscriber(self, msg: HandCmd_, datatype: str = "") -> None:
        try:
            cmd_data = self._process_hand_command(msg)
            if cmd_data and self.output_shm:
                self.output_shm.write_data({"motor_cmd": cmd_data})
        except Exception as e:
            print(f"dg5f_dds [{self.node_name}] error handling command: {e}")

    @staticmethod
    def _process_hand_command(msg: HandCmd_) -> Dict[str, Any]:
        n = len(msg.motor_cmd)
        return {
            "positions": [float(msg.motor_cmd[i].q) for i in range(n)],
            "velocities": [float(msg.motor_cmd[i].dq) for i in range(n)],
            "torques": [float(msg.motor_cmd[i].tau) for i in range(n)],
            "kp": [float(msg.motor_cmd[i].kp) for i in range(n)],
            "kd": [float(msg.motor_cmd[i].kd) for i in range(n)],
        }

    # ------------------------------------------------------------------ #
    # Publisher (SHM → DDS)                                              #
    # ------------------------------------------------------------------ #

    def dds_publisher(self) -> Any:
        """Read isaac_dg5f_state from SHM and publish HandState_.

        Expected SHM layout:
            {"positions": [20 q], "velocities": [20 dq], "torques": [20 tau]}
        """
        try:
            data = self.input_shm.read_data() or {}
            if not data or "positions" not in data:
                return None

            positions = data.get("positions", [])
            velocities = data.get("velocities", [])
            torques = data.get("torques", [])
            n = min(N_MOTORS, len(positions))
            for i in range(n):
                m = self.hand_state.motor_state[i]
                m.q = float(positions[i])
                if i < len(velocities):
                    m.dq = float(velocities[i])
                if i < len(torques):
                    m.tau_est = float(torques[i])

            if self.state_publisher:
                self.state_publisher.Write(self.hand_state)
        except Exception as e:
            print(f"dg5f_dds [{self.node_name}] error publishing state: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Helpers used by obs writer + action provider                       #
    # ------------------------------------------------------------------ #

    def write_dg5f_state(self, positions, velocities, torques) -> None:
        """Helper for the observation writer to push a snapshot into SHM."""
        try:
            data = {
                "positions": positions.tolist() if hasattr(positions, "tolist") else list(positions),
                "velocities": velocities.tolist() if hasattr(velocities, "tolist") else list(velocities),
                "torques": torques.tolist() if hasattr(torques, "tolist") else list(torques),
            }
            if self.input_shm:
                self.input_shm.write_data(data)
        except Exception as e:
            print(f"dg5f_dds [{self.node_name}] error writing state SHM: {e}")

    def get_dg5f_command(self) -> Optional[Dict[str, Any]]:
        """Read latest cmd from SHM (action_provider consumes this)."""
        if self.output_shm:
            return self.output_shm.read_data()
        return None
