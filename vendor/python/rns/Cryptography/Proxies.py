# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from .X25519 import X25519PrivateKey as X25519PrivateKeyInternal, X25519PublicKey as X25519PublicKeyInternal
from .Ed25519 import Ed25519PrivateKey as Ed25519PrivateKeyInternal, Ed25519PublicKey as Ed25519PublicKeyInternal

class X25519PrivateKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def generate(cls):
        return cls(X25519PrivateKeyInternal.generate())

    @classmethod
    def from_private_bytes(cls, data):
        return cls(X25519PrivateKeyInternal.from_private_bytes(data))

    def private_bytes(self):
        return self.real.private_bytes()

    def public_key(self):
        return X25519PublicKeyProxy(self.real.public_key())

    def exchange(self, peer_public_key):
        if isinstance(peer_public_key, X25519PublicKeyProxy):
            return self.real.exchange(peer_public_key.real)
        else:
            return self.real.exchange(peer_public_key)


class X25519PublicKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def from_public_bytes(cls, data):
        return cls(X25519PublicKeyInternal.from_public_bytes(data))

    def public_bytes(self):
        return self.real.public_bytes()


class Ed25519PrivateKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def generate(cls):
        return cls(Ed25519PrivateKeyInternal.generate())

    @classmethod
    def from_private_bytes(cls, data):
        return cls(Ed25519PrivateKeyInternal.from_private_bytes(data))

    def private_bytes(self):
        return self.real.private_bytes()

    def public_key(self):
        return Ed25519PublicKeyProxy(self.real.public_key())

    def sign(self, message):
        return self.real.sign(message)


class Ed25519PublicKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def from_public_bytes(cls, data):
        return cls(Ed25519PublicKeyInternal.from_public_bytes(data))

    def public_bytes(self):
        return self.real.public_bytes()

    def verify(self, signature, message):
        self.real.verify(signature, message)
