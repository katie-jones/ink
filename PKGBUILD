# Maintainer: Katie Jones <k.jo133@gmail.com>
pkgname=ink
pkgver=0.1
pkgrel=1
pkgdesc="A backup manager"
arch=('any')
url="https://github.com/katie-jones/ink"
license=('GPL')
groups=()
depends=('python>=3.5')
makedepends=('git')
optdepends=('systemd: For scheduling runs')
provides=()
conflicts=()
replaces=()
backup=()
options=()
install=
changelog=
source=('git+git://github.com/katie-jones/ink.git')
noextract=()
md5sums=('SKIP')

check() {
    cd "$pkgname"
    python -m unittest test_ink.py
}

package() {
  cd "$pkgname"

  # Copy ink to /usr/bin
  mkdir -p "$pkgdir/usr/bin/"
  cp "ink.py" "$pkgdir/usr/bin/ink"
}
