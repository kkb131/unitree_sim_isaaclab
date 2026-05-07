#!/usr/bin/env python3
"""
Combine UR10e URDF + DG-5F (right) URDF into a single articulation by adding
a fixed mount joint between UR10e `tool0` and DG-5F `rl_dg_mount`.

Used by tools/build_ur10e_dg5f_assets.sh; can also be run standalone.
"""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

UR10E_MOUNT_LINK = "tool0"
DG5F_ROOT_LINK = "rl_dg_mount"
MOUNT_JOINT_NAME = "ur10e_to_dg5f_mount"
MOUNT_XYZ = "0 0 0"
MOUNT_RPY = "0 0 0"


def collect_link_names(tree: ET.ElementTree) -> set[str]:
    return {l.get("name") for l in tree.getroot().findall("link") if l.get("name")}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ur10e", required=True, type=Path, help="UR10e URDF (xacro-compiled)")
    p.add_argument("--dg5f", required=True, type=Path, help="DG-5F URDF (mesh paths absolute)")
    p.add_argument("--out", required=True, type=Path, help="Output combined URDF")
    args = p.parse_args()

    ur = ET.parse(args.ur10e)
    dg = ET.parse(args.dg5f)

    ur_links = collect_link_names(ur)
    dg_links = collect_link_names(dg)
    if UR10E_MOUNT_LINK not in ur_links:
        raise SystemExit(f"UR10e missing expected link '{UR10E_MOUNT_LINK}'")
    if DG5F_ROOT_LINK not in dg_links:
        raise SystemExit(f"DG-5F missing expected link '{DG5F_ROOT_LINK}'")
    overlap = ur_links & dg_links
    if overlap:
        raise SystemExit(f"Link name collision: {overlap}")

    out = ET.Element("robot", {"name": "ur10e_with_dg5f"})
    for child in list(ur.getroot()):
        out.append(child)
    for child in list(dg.getroot()):
        if child.tag in ("link", "joint", "transmission", "gazebo", "material"):
            out.append(child)

    mount = ET.SubElement(out, "joint", {"name": MOUNT_JOINT_NAME, "type": "fixed"})
    ET.SubElement(mount, "parent", {"link": UR10E_MOUNT_LINK})
    ET.SubElement(mount, "child", {"link": DG5F_ROOT_LINK})
    ET.SubElement(mount, "origin", {"xyz": MOUNT_XYZ, "rpy": MOUNT_RPY})

    ET.indent(out, space="  ")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("<?xml version=\"1.0\"?>\n" + ET.tostring(out, encoding="unicode"))

    n_links = len(out.findall("link"))
    n_joints = len(out.findall("joint"))
    n_revolute = sum(1 for j in out.findall("joint") if j.get("type") == "revolute")
    print(f"wrote {args.out}")
    print(f"  links: {n_links}, joints: {n_joints} (revolute: {n_revolute})")


if __name__ == "__main__":
    main()
