/**
Test to check the Java System module
for system properties
*/

public class Test {
    public static void main(String[] args) {
        try {
            assert System.getenv("property1") != null;
            System.out.println(System.getProperty("property1"));
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
