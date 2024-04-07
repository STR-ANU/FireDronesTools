/*
  translation of pymavlink rotmat class to javascript
  */

class Vector3 {
    constructor(x = 0, y = 0, z = 0) {
        if (Array.isArray(x) && x.length === 3) {
            [this.x, this.y, this.z] = x.map(Number);
        } else if (typeof x === 'number' && typeof y === 'number' && typeof z === 'number') {
            this.x = Number(x);
            this.y = Number(y);
            this.z = Number(z);
        } else {
            throw new Error('Invalid initializer for Vector3');
        }
    }

    toString() {
        return `Vector3(${this.x.toFixed(2)}, ${this.y.toFixed(2)}, ${this.z.toFixed(2)})`;
    }

    equals(v) {
        return this.x === v.x && this.y === v.y && this.z === v.z;
    }

    close(v, tol = 1e-7) {
        return Math.abs(this.x - v.x) < tol &&
               Math.abs(this.y - v.y) < tol &&
               Math.abs(this.z - v.z) < tol;
    }

    add(v) {
        return new Vector3(this.x + v.x, this.y + v.y, this.z + v.z);
    }

    subtract(v) {
        return new Vector3(this.x - v.x, this.y - v.y, this.z - v.z);
    }

    negate() {
        return new Vector3(-this.x, -this.y, -this.z);
    }

    multiply(v) {
        if (v instanceof Vector3) {
            // Dot product
            return this.x * v.x + this.y * v.y + this.z * v.z;
        } else {
            // Scalar multiplication
            return new Vector3(this.x * v, this.y * v, this.z * v);
        }
    }

    divide(v) {
        return new Vector3(this.x / v, this.y / v, this.z / v);
    }

    cross(v) {
        // Cross product
        return new Vector3(
            this.y * v.z - this.z * v.y,
            this.z * v.x - this.x * v.z,
            this.x * v.y - this.y * v.x
        );
    }

    length() {
        return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z);
    }

    zero() {
        this.x = 0;
        this.y = 0;
        this.z = 0;
    }

    angle(v) {
        const dotProduct = this.multiply(v);
        return Math.acos(dotProduct / (this.length() * v.length()));
    }

    normalized() {
        const len = this.length();
        if (len === 0) {
            return new Vector3(0, 0, 0);
        }
        return this.divide(len);
    }

    normalize() {
        const norm = this.normalized();
        this.x = norm.x;
        this.y = norm.y;
        this.z = norm.z;
    }
}

class Matrix3 {
    constructor(a = null, b = null, c = null) {
        if (a !== null && b !== null && c !== null) {
            this.a = { ...a };
            this.b = { ...b };
            this.c = { ...c };
        } else {
            this.identity();
        }
    }

    toString() {
        return `Matrix3((${this.a.x.toFixed(2)}, ${this.a.y.toFixed(2)}, ${this.a.z.toFixed(2)}), ` +
               `(${this.b.x.toFixed(2)}, ${this.b.y.toFixed(2)}, ${this.b.z.toFixed(2)}), ` +
               `(${this.c.x.toFixed(2)}, ${this.c.y.toFixed(2)}, ${this.c.z.toFixed(2)}))`;
    }

    identity() {
        this.a = new Vector3(1, 0, 0);
        this.b = new Vector3(0, 1, 0);
        this.c = new Vector3(0, 0, 1);
    }

    transposed() {
        return new Matrix3(
            new Vector3(this.a.x, this.b.x, this.c.x),
            new Vector3(this.a.y, this.b.y, this.c.y),
            new Vector3(this.a.z, this.b.z, this.c.z)
        );
    }

    fromEuler(roll, pitch, yaw) {
        let cp = Math.cos(pitch);
        let sp = Math.sin(pitch);
        let sr = Math.sin(roll);
        let cr = Math.cos(roll);
        let sy = Math.sin(yaw);
        let cy = Math.cos(yaw);

        this.a.x = cp * cy;
        this.a.y = sr * sp * cy - cr * sy;
        this.a.z = cr * sp * cy + sr * sy;
        this.b.x = cp * sy;
        this.b.y = sr * sp * sy + cr * cy;
        this.b.z = cr * sp * sy - sr * cy;
        this.c.x = -sp;
        this.c.y = sr * cp;
        this.c.z = cr * cp;
    }

    // Implement additional methods
    determinant() {
        let ret = this.a.x * (this.b.y * this.c.z - this.b.z * this.c.y) +
                  this.a.y * (this.b.z * this.c.x - this.b.x * this.c.z) +
                  this.a.z * (this.b.x * this.c.y - this.b.y * this.c.x);
        return ret;
    }

    invert() {
        let d = this.determinant();
        if (d === 0) return null; // No inverse if determinant is 0

        let inv = new Matrix3();
        inv.a.x = (this.b.y * this.c.z - this.c.y * this.b.z) / d;
        inv.a.y = (this.a.z * this.c.y - this.a.y * this.c.z) / d;
        inv.a.z = (this.a.y * this.b.z - this.a.z * this.b.y) / d;
        inv.b.x = (this.b.z * this.c.x - this.b.x * this.c.z) / d;
        inv.b.y = (this.a.x * this.c.z - this.a.z * this.c.x) / d;
        inv.b.z = (this.a.x * this.b.z - this.a.z * this.b.x) / d;
        inv.c.x = (this.b.x * this.c.y - this.c.x * this.b.y) / d;
        inv.c.y = (this.a.y * this.c.x - this.a.x * this.c.y) / d;
        inv.c.z = (this.a.x * this.b.y - this.b.x * this.a.y) / d;
        return inv;
    }

    add(m) {
        return new Matrix3(
            this.a.add(m.a),
            this.b.add(m.b),
            this.c.add(m.c)
        );
    }

    subtract(m) {
        return new Matrix3(
            this.a.subtract(m.a),
            this.b.subtract(m.b),
            this.c.subtract(m.c)
        );
    }

    multiply(other) {
        if (other instanceof Matrix3) {
            // Matrix multiplication
            let a = new Vector3(
                this.a.x * other.a.x + this.a.y * other.b.x + this.a.z * other.c.x,
                this.a.x * other.a.y + this.a.y * other.b.y + this.a.z * other.c.y,
                this.a.x * other.a.z + this.a.y * other.b.z + this.a.z * other.c.z
            );
            let b = new Vector3(
                this.b.x * other.a.x + this.b.y * other.b.x + this.b.z * other.c.x,
                this.b.x * other.a.y + this.b.y * other.b.y + this.b.z * other.c.y,
                this.b.x * other.a.z + this.b.y * other.b.z + this.b.z * other.c.z
            );
            let c = new Vector3(
                this.c.x * other.a.x + this.c.y * other.b.x + this.c.z * other.c.x,
                this.c.x * other.a.y + this.c.y * other.b.y + this.c.z * other.c.y,
                this.c.x * other.a.z + this.c.y * other.b.z + this.c.z * other.c.z
            );
            return new Matrix3(a, b, c);
        } else if (other instanceof Vector3) {
            // Multiplying matrix by vector
            return new Vector3(
                this.a.x * other.x + this.a.y * other.y + this.a.z * other.z,
                this.b.x * other.x + this.b.y * other.y + this.b.z * other.z,
                this.c.x * other.x + this.c.y * other.y + this.c.z * other.z
            );
        } else {
            // Assuming scalar multiplication
            return new Matrix3(
                this.a.multiply(other),
                this.b.multiply(other),
                this.c.multiply(other)
            );
        }
    }

    equals(m) {
        return this.a.equals(m.a) && this.b.equals(m.b) && this.c.equals(m.c);
    }
}
