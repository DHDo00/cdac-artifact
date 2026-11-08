package com.android.server.iguard;

interface IIguardDemoService {
    String ping();
    String readSecret();
    String readPublic();
    String readByPath(String path);
    String writePublic();
    String toctouWritePublicRace(int rounds);
    String reportOnlyThenReturn();
    String reportThenThrow();
    String readPublicPlain();
}
