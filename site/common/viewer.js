// Small three.js viewer: orbit / zoom a triangle soup, either as mounted on the wall or as printed on the bed.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

export class Viewer {
  constructor(el) {
    this.el = el;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    el.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 1, 5000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.8); sun.position.set(300, 500, 400); this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0xffffff, 0.6); fill.position.set(-300, -100, -200); this.scene.add(fill);
    this.part = new THREE.Group(); this.context = new THREE.Group();
    this.scene.add(this.part, this.context);
    this.mode = "mounted";
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    const loop = () => { this.controls.update(); this.renderer.render(this.scene, this.camera); requestAnimationFrame(loop); };
    loop();
  }

  resize() {
    const w = this.el.clientWidth, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  // tris: Float32Array in print coords (X = out from wall, Y = up when mounted, Z = along the wall / up when printed)
  // wall: {pitch, open, lip} slatwall section drawn behind the part in the mounted view
  show(tris, { wall, keepView = false } = {}) {
    this.tris = tris; this.wall = wall;
    this.part.clear();
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(tris, 3));
    g.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ color: css("--part") || "#e8892f", roughness: 0.55, metalness: 0.0, flatShading: true });
    this.part.add(new THREE.Mesh(g, mat));
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 30), new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.18 }));
    this.part.add(edges);
    const r = new THREE.Box3().setFromBufferAttribute(g.getAttribute("position")).getSize(new THREE.Vector3()).length();
    const same = this.frameR && Math.abs(r / this.frameR - 1) < 0.25;   // keep the user's view unless the part changed size a lot
    this.setMode(this.mode, keepView && same);
  }

  setMode(mode, keepView = false) {
    this.mode = mode;
    if (!this.tris) return;
    const box = new THREE.Box3().setFromBufferAttribute(new THREE.BufferAttribute(this.tris, 3));
    this.context.clear();
    this.part.rotation.set(0, 0, 0); this.part.position.set(0, 0, 0);
    const grey = new THREE.MeshStandardMaterial({ color: css("--wall") || "#3a3f46", roughness: 0.9, transparent: true, opacity: 0.55 });
    if (mode === "mounted" && this.wall) {
      const { pitch, open, lip } = this.wall, zLen = box.max.z - box.min.z + 160, zMid = (box.max.z + box.min.z) / 2;
      for (let k = -3; k <= 1; k++) {                    // slats between the slot openings, face at x = 0
        const y0 = k * pitch + open, y1 = (k + 1) * pitch;
        const slat = new THREE.Mesh(new THREE.BoxGeometry(lip, y1 - y0, zLen), grey);
        slat.position.set(-lip / 2, (y0 + y1) / 2, zMid); this.context.add(slat);
      }
      const back = new THREE.Mesh(new THREE.BoxGeometry(2, 5 * pitch, zLen), grey);
      back.position.set(-24, -1.5 * pitch + open, zMid); this.context.add(back);
    } else if (mode === "printed") {
      this.part.rotation.x = -Math.PI / 2;               // print Z (shelf width) points up
      const b = new THREE.Box3().setFromObject(this.part);
      this.part.position.set(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
      const bed = new THREE.Mesh(new THREE.BoxGeometry(250, 2, 210), grey);
      bed.position.y = -1; this.context.add(bed);
      const grid = new THREE.GridHelper(250, 25, 0x888888, 0x666666); grid.position.y = 0.05;
      grid.scale.z = 210 / 250; this.context.add(grid);
    }
    if (!keepView) this.frame();
  }

  frame() {
    const b = new THREE.Box3().setFromObject(this.part), c = b.getCenter(new THREE.Vector3()), r = b.getSize(new THREE.Vector3()).length();
    this.frameR = r;
    const dir = this.mode === "printed" ? new THREE.Vector3(0.9, 0.9, 1.1) : new THREE.Vector3(1.2, 0.55, 0.9);
    this.camera.position.copy(c).add(dir.normalize().multiplyScalar(r * 1.6));
    this.controls.target.copy(c); this.controls.update();
  }
}
