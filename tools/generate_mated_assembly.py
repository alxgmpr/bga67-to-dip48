#!/usr/bin/env python3
"""Build and render the actual base/carrier STEP exports in the mated pose."""

from pathlib import Path

import cadquery as cq
import vtk


ROOT = Path(__file__).resolve().parents[1]
BASE_STEP = ROOT / "mechanical" / "base-assembly.step"
CARRIER_STEP = ROOT / "mechanical" / "carrier-assembly.step"
OUTPUT_STEP = ROOT / "mechanical" / "mated-assembly.step"
OUTPUT_PNG = ROOT / "mechanical" / "renders" / "mated-assembly.png"

# KiCad STEP coordinates use (PCB X, -PCB Y).  The base is rotated -90 degrees
# about its J1 mating centre so base pin 1 and carrier pin 1 share orientation.
BASE_J1 = (124.1, -91.2)
CARRIER_J1 = (168.3682, -85.53)
BASE_PAD1_VECTOR = (-1.54, 2.8)
CARRIER_PAD1_VECTOR = (2.8, 1.355)
CARRIER_TOP_Z = 1.5162
MATED_HEIGHT = 4.0


def transformed_base():
    base = cq.importers.importStep(str(BASE_STEP)).val()
    base = base.translate((-BASE_J1[0], -BASE_J1[1], 0))
    base = base.rotate((0, 0, 0), (0, 0, 1), -90)
    return base.translate((CARRIER_J1[0], CARRIER_J1[1], CARRIER_TOP_Z + MATED_HEIGHT))


def vtk_actor(shape, color):
    vertices, triangles = shape.tessellate(0.08)
    points = vtk.vtkPoints()
    for vertex in vertices:
        points.InsertNextPoint(vertex.x, vertex.y, vertex.z)
    cells = vtk.vtkCellArray()
    for triangle in triangles:
        cell = vtk.vtkTriangle()
        for index, vertex_index in enumerate(triangle):
            cell.GetPointIds().SetId(index, vertex_index)
        cells.InsertNextCell(cell)
    mesh = vtk.vtkPolyData()
    mesh.SetPoints(points)
    mesh.SetPolys(cells)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(mesh)
    normals.SetFeatureAngle(45)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetSpecular(0.25)
    actor.GetProperty().SetSpecularPower(20)
    return actor


def render(base, carrier):
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.035, 0.045, 0.055)
    renderer.AddActor(vtk_actor(base, (0.18, 0.43, 0.27)))
    renderer.AddActor(vtk_actor(carrier, (0.86, 0.42, 0.10)))

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(True)
    window.SetSize(1800, 1200)
    window.AddRenderer(renderer)
    camera = renderer.GetActiveCamera()
    camera.SetFocalPoint(CARRIER_J1[0], CARRIER_J1[1], 2.8)
    camera.SetPosition(CARRIER_J1[0] + 24, CARRIER_J1[1] - 32, -20)
    camera.SetViewUp(0, 0, 1)
    camera.ParallelProjectionOn()
    camera.SetParallelScale(17)
    renderer.ResetCameraClippingRange()
    window.Render()

    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetScale(1)
    capture.ReadFrontBufferOff()
    capture.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(OUTPUT_PNG))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()


def main():
    # Redundant geometric assertion documents the chosen 90-degree mating
    # orientation independently of the netlist check.
    rotated_base_pin1 = (BASE_PAD1_VECTOR[1], -BASE_PAD1_VECTOR[0])
    assert rotated_base_pin1[0] == CARRIER_PAD1_VECTOR[0]
    assert rotated_base_pin1[1] * CARRIER_PAD1_VECTOR[1] > 0

    base = transformed_base()
    carrier = cq.importers.importStep(str(CARRIER_STEP)).val()
    assembly = cq.Assembly(name="BGA67_DF40_DIP48_mated")
    assembly.add(carrier, name="carrier", color=cq.Color(0.20, 0.34, 0.48))
    assembly.add(base, name="base", color=cq.Color(0.18, 0.43, 0.27))
    OUTPUT_STEP.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    assembly.save(str(OUTPUT_STEP), mode="default")
    render(base, carrier)
    print(OUTPUT_STEP)
    print(OUTPUT_PNG)


if __name__ == "__main__":
    main()
