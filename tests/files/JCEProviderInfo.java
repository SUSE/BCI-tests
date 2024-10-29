import java.security.Provider;
import java.security.Provider.Service;
import java.security.Security;

public class JCEProviderInfo {
    public static void main(final String[] args) {
        System.err.printf("JCE Provider Info: %s %s/%s on %s %s%n", System.getProperty("java.vm.name"),
                          System.getProperty("java.runtime.version"),
                          System.getProperty("java.vm.version"),
                          System.getProperty("os.name"),
                          System.getProperty("os.version"));

        System.err.printf("Listing all JCA Security Providers%n");
        final Provider[] providers = Security.getProviders();
        if (providers.length == 0) {
            System.err.println("no providers available");
            System.exit(1);
        }
        for (final Provider p : providers) {
            System.out.printf("--- Provider %s %s%n    info %s%n", p.getName(), p.getVersionStr(), p.getInfo());
            for(Service s : p.getServices()) {
                System.out.printf(" + %s.%s : %s (%s)%n  tostring=%s%n", s.getType(), s.getAlgorithm(), s.getClassName(), s.getProvider().getName(), s.toString());
            }
        }
    }
}