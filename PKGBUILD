# Maintainer: Katie Jones <k.jo133@gmail.com>
pkgname=ink-git
pkgver=1.0
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
    cd "$pkgname"/source
    python -m unittest test_ink.py
}

package() {
  # Change to source directory
  cd "$pkgname"/source

  # Install using setup.py
  python setup.py install --root="$pkgname" --prefix="/usr"
}
