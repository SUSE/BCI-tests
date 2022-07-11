/**
Test to check the Java File module.
It consists on:
- Text and binary file read and write
- File operations (e.g. exists, permissions, rename and delete)
- Directory operations (e.g. read content, creation)
*/
import java.io.*;
import java.io.IOException;
import java.util.UUID;

class Test {
    static String textContent = "Content of the text file";

    static void createTextFile(String filepath) throws IOException{
        FileWriter file = new FileWriter(filepath);
        file.write(Test.textContent);
        file.close();
    }

    static void readTextFile(String filepath) throws IOException {
        FileReader file = new FileReader(filepath);
        char [] a = new char[1024];
        int length = file.read(a);
        String output = "";
        for(int i=0; i<length; i++)
            output = output + a[i];
        file.close();
    }

    static void createBinaryFile(String inputFile, String outputFile) throws IOException {
        InputStream inputStream = new FileInputStream(inputFile);
        OutputStream outputStream = new FileOutputStream(outputFile);

        int byteRead = -1;
        while ((byteRead = inputStream.read()) != -1) {
            outputStream.write((byte)byteRead);
        }

        inputStream.close();
        outputStream.close();
    }

    static void findFile(String dirpath, String filename) throws Exception {
        boolean exists = false;
        File[] files = new File(dirpath).listFiles();
        for (int i = 0; i < files.length; i++) {
            if (files[i].getName().equals(filename))
                exists = true;
        }
        
        assert exists;
    }

    public static void main(String[] args) {
        UUID fileuuid=UUID.randomUUID();
        
        String dirpath = "/tmp";
        String textfile =  dirpath + "/" + fileuuid + ".txt";
        String binaryfile = dirpath + "/" + fileuuid + ".bin";
        String binaryfile2 = dirpath + "/" + fileuuid + ".data";
        

        try {
            // Text files tests
            Test.createTextFile(textfile);
            Test.readTextFile(textfile);

            // Binary files tests
            Test.createBinaryFile(textfile, binaryfile);
            Test.readTextFile(binaryfile);

            // Files tests
            assert new File(textfile).length() == Test.textContent.length();
            assert new File(textfile).exists() == true;
            assert new File(textfile).isFile();
            new File(binaryfile).renameTo(new File(binaryfile2));
            new File(binaryfile2).delete();
            assert new File(textfile).canRead() == true;
            assert new File(textfile).canWrite() == true;
            new File(textfile).setExecutable(true);
            assert new File(textfile).canExecute() == true;

            // Directories tests
            assert new File(dirpath).isDirectory();
            new File(dirpath + "/extra").mkdir();
            Test.findFile(dirpath, fileuuid + ".txt");
            
            // General
            new File(dirpath).getFreeSpace();
            File f = File.createTempFile("" + fileuuid, ".tmp");

            System.out.println("All OK");
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }

        
    }
}
